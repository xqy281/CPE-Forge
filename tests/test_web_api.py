"""
Web API 单元测试 — 使用 Flask 测试客户端 + Mock Pipeline

验证所有 HTTP 端点的请求/响应格式，不依赖真实文件系统或 LLM 调用。
"""
import pytest
from datetime import datetime

from web.app import create_app
from pipeline.models import AnalysisResult


# =============================================================================
# Mock 对象
# =============================================================================

class DummyModelConfig:
    """模拟 LLMModelConfig 的安全字典输出"""

    def to_safe_dict(self):
        return {"model_id": "test-model", "display_name": "Test Model"}


class DummyPipelineAPI:
    """模拟 CPEPipelineAPI —— 方法签名与 api_routes.py 中的调用方式精确对齐"""

    def __init__(self, *args, **kwargs):
        self.invoked = []

    def get_employee_list(self):
        self.invoked.append("get_employee_list")
        return [{"name": "测试员", "email": "test@jointelli.com"}]

    def get_employee_report_ranges(self, email):
        self.invoked.append(f"get_employee_report_ranges:{email}")
        return [{"start": "2025-01-01", "end": "2025-01-07", "id": "2025-01-01_2025-01-07"}]

    def get_analysis_result(self, email):
        self.invoked.append(f"get_analysis_result:{email}")
        if email == "notfound@jointelli.com":
            return None
        return AnalysisResult(
            employee_email=email,
            employee_name="测试员",
            date_range_ids=["2025-01-01_2025-01-07"],
            model_id="test-model",
            token_estimate={"token_count": 100},
            profile={"radar_outer": {}},
            growth={"closed_loop_issues": []},
            generated_at=datetime.now().isoformat(),
            elapsed_seconds=10.0,
        )

    def estimate_tokens(self, email, date_range_ids, model):
        """注意：参数名与真实 API 签名一致（date_range_ids, model）"""
        self.invoked.append(f"estimate_tokens:{email}")
        return {
            "token_count": 1500,
            "level": "green",
            "level_label": "🟢绿色",
        }

    def run_full_analysis(self, email, date_range_ids, model_id):
        self.invoked.append("run_full_analysis")
        return self.get_analysis_result(email)

    def run_profile_only(self, email, date_range_ids, model_id):
        self.invoked.append("run_profile_only")
        return {"radar_outer": "test"}

    def run_growth_only(self, email, date_range_ids, model_id):
        self.invoked.append("run_growth_only")
        return {"growth_analysis": "test"}

    def start_chat_session(self, email, date_range_ids, model_id):
        self.invoked.append("start_chat_session")
        return "fake-session-123"

    def chat(self, session_id, message):
        self.invoked.append("chat")
        if session_id != "fake-session-123":
            raise KeyError(f"会话 {session_id} 不存在或已过期")
        return {"role": "assistant", "content": "测试回复", "turn": 2}

    def get_chat_history(self, session_id):
        self.invoked.append("get_chat_history")
        if session_id != "fake-session-123":
            raise KeyError(f"会话 {session_id} 不存在或已过期")
        return [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app(monkeypatch):
    """创建带有 Mock Pipeline 的 Flask 测试应用"""
    from web import api_routes

    dummy = DummyPipelineAPI()
    # 替换 get_pipeline 工厂函数，使其返回我们的 Mock 对象
    monkeypatch.setattr(api_routes, "get_pipeline", lambda: dummy)
    # 替换 list_model_configs，避免真实文件系统访问
    monkeypatch.setattr(api_routes, "list_model_configs", lambda enabled_only=False: [DummyModelConfig()])

    test_app = create_app()
    test_app.config["TESTING"] = True
    test_app.dummy_api = dummy
    yield test_app


@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


# =============================================================================
# GET 端点测试
# =============================================================================

class TestGetEndpoints:
    """验证所有 GET 类端点"""

    def test_get_cleaning_report(self, client, app, tmp_path):
        """获取清洗报告 — 正常路径"""
        # 创建模拟的 cleaning_report.json
        report_data = {
            "总文件数": 710,
            "有效文件": 622,
            "被过滤文件": 70,
            "加密文件": 2,
            "损坏文件": 0,
            "Sheet总数": 711,
            "去重后Sheet数": 582,
            "重复组数": 81,
            "去重率": "18.1%",
            "员工明细": {
                "test@jointelli.com": 50,
            },
            "加密文件清单": [
                "attachments\\test@jointelli.com\\工作周报_测试(2025年8月25日-2025年8月30日).xlsx",
                "attachments\\test@jointelli.com\\工作周报_测试(2025年9月1日-2025年9月6日).xlsx",
            ],
        }
        import json, tempfile, os
        output_dir = app.config["OUTPUT_DIR"]
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(str(output_dir), "cleaning_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False)

        try:
            resp = client.get("/api/cleaning-report")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["total_files"] == 710
            assert data["valid_files"] == 622
            assert data["dedup_rate"] == "18.1%"
            assert len(data["employees"]) == 1
            assert data["employees"][0]["report_count"] == 50
            assert "test@jointelli.com" in data["encrypted_by_employee"]
            assert len(data["encrypted_by_employee"]["test@jointelli.com"]) == 2
        finally:
            if os.path.exists(report_path):
                os.remove(report_path)

    def test_get_cleaning_report_not_found(self, client):
        """获取清洗报告 — 文件不存在时返回 404"""
        resp = client.get("/api/cleaning-report")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_get_employees(self, client, app):
        """获取员工列表 — 正常路径"""
        resp = client.get("/api/employees")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "测试员"
        assert data[0]["email"] == "test@jointelli.com"
        assert "get_employee_list" in app.dummy_api.invoked

    def test_get_ranges(self, client, app):
        """获取员工时间范围列表 — 正常路径"""
        resp = client.get("/api/employees/test@jointelli.com/ranges")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["id"] == "2025-01-01_2025-01-07"
        assert "get_employee_report_ranges:test@jointelli.com" in app.dummy_api.invoked

    def test_get_models(self, client):
        """获取 LLM 模型列表 — 正常路径"""
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["model_id"] == "test-model"

    def test_get_latest_analysis_found(self, client, app):
        """获取最近分析结果 — 存在缓存"""
        resp = client.get("/api/analysis/test@jointelli.com/latest")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["employee_email"] == "test@jointelli.com"
        # to_web_response 应排除 markdown_content
        assert "markdown_content" not in data

    def test_get_latest_analysis_not_found(self, client):
        """获取最近分析结果 — 无缓存时返回 404"""
        resp = client.get("/api/analysis/notfound@jointelli.com/latest")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_get_analysis_history_includes_date_range_ids(self, client, app):
        """获取历史分析列表 — 每条记录应包含 date_range_ids 字段"""
        import json, os

        output_dir = app.config["OUTPUT_DIR"]
        emp_dir = os.path.join(str(output_dir), "test@jointelli.com")
        os.makedirs(emp_dir, exist_ok=True)

        # 创建模拟分析结果文件
        mock_analysis = {
            "generated_at": "2026-03-11T10:00:00",
            "model_id": "deepseek/deepseek-reasoner",
            "date_range_ids": [
                "2025-01-06_2025-01-11",
                "2025-01-13_2025-01-17",
                "2025-01-19_2025-01-23",
            ],
            "elapsed_seconds": 120.5,
        }
        filepath = os.path.join(emp_dir, "20260311_100000_analysis.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(mock_analysis, f, ensure_ascii=False)

        try:
            resp = client.get("/api/analysis/test@jointelli.com/history")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data) >= 1

            # 验证返回的记录中包含 date_range_ids 字段
            record = data[0]
            assert "date_range_ids" in record, "历史记录应包含 date_range_ids 字段"
            assert record["date_range_ids"] == [
                "2025-01-06_2025-01-11",
                "2025-01-13_2025-01-17",
                "2025-01-19_2025-01-23",
            ]
            assert record["date_range_count"] == 3
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
            if os.path.exists(emp_dir):
                try:
                    os.rmdir(emp_dir)
                except OSError:
                    pass


# =============================================================================
# POST 端点测试
# =============================================================================

class TestPostEndpoints:
    """验证所有 POST 类端点"""

    def test_estimate_tokens_success(self, client, app):
        """Token 预估 — 正常路径"""
        payload = {"email": "test@jointelli.com", "range_ids": ["2025-01-01"], "model_id": "test-model"}
        resp = client.post("/api/estimate-tokens", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["token_count"] == 1500
        assert data["level"] == "green"
        assert "estimate_tokens:test@jointelli.com" in app.dummy_api.invoked

    def test_estimate_tokens_missing_email(self, client):
        """Token 预估 — 缺少 email 字段返回 400"""
        resp = client.post("/api/estimate-tokens", json={"range_ids": ["1"]})
        assert resp.status_code == 400

    def test_estimate_tokens_missing_range_ids(self, client):
        """Token 预估 — 缺少 range_ids 字段返回 400"""
        resp = client.post("/api/estimate-tokens", json={"email": "test"})
        assert resp.status_code == 400

    def test_estimate_tokens_empty_body(self, client):
        """Token 预估 — 空请求体返回 400"""
        resp = client.post("/api/estimate-tokens", content_type="application/json")
        assert resp.status_code == 400

    def test_run_full_analysis(self, client, app):
        """完整分析 — 正常路径"""
        payload = {"email": "test@jointelli.com", "range_ids": ["2025-01-01"], "model_id": "test-model"}
        resp = client.post("/api/analysis/full", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["employee_email"] == "test@jointelli.com"
        assert "run_full_analysis" in app.dummy_api.invoked

    def test_run_full_analysis_missing_fields(self, client):
        """完整分析 — 缺少必填字段返回 400"""
        resp = client.post("/api/analysis/full", json={"email": "test"})
        assert resp.status_code == 400

    def test_run_profile_only(self, client, app):
        """画像提取 — 正常路径"""
        payload = {"email": "test", "range_ids": ["1"], "model_id": "m1"}
        resp = client.post("/api/analysis/profile", json=payload)
        assert resp.status_code == 200
        assert "radar_outer" in resp.get_json()
        assert "run_profile_only" in app.dummy_api.invoked

    def test_run_growth_only(self, client, app):
        """成长分析 — 正常路径"""
        payload = {"email": "test", "range_ids": ["1"], "model_id": "m1"}
        resp = client.post("/api/analysis/growth", json=payload)
        assert resp.status_code == 200
        assert "growth_analysis" in resp.get_json()
        assert "run_growth_only" in app.dummy_api.invoked


# =============================================================================
# FAQ 对话端点测试
# =============================================================================

class TestChatEndpoints:
    """验证 FAQ 对话相关端点"""

    def test_chat_start(self, client, app):
        """创建对话会话 — 正常路径"""
        payload = {"email": "test", "range_ids": ["1"], "model_id": "m1"}
        resp = client.post("/api/chat/start", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["session_id"] == "fake-session-123"
        assert "start_chat_session" in app.dummy_api.invoked

    def test_chat_start_missing_fields(self, client):
        """创建对话会话 — 缺少字段返回 400"""
        resp = client.post("/api/chat/start", json={"email": "test"})
        assert resp.status_code == 400

    def test_chat_send(self, client, app):
        """发送对话消息 — 正常路径"""
        payload = {"session_id": "fake-session-123", "message": "你好"}
        resp = client.post("/api/chat/send", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["content"] == "测试回复"
        assert data["role"] == "assistant"
        assert data["turn"] == 2
        assert "chat" in app.dummy_api.invoked

    def test_chat_send_invalid_session(self, client):
        """发送消息 — 无效会话返回 404"""
        payload = {"session_id": "bad-session", "message": "hello"}
        resp = client.post("/api/chat/send", json=payload)
        assert resp.status_code == 404

    def test_chat_send_missing_fields(self, client):
        """发送消息 — 缺少字段返回 400"""
        resp = client.post("/api/chat/send", json={"session_id": "123"})
        assert resp.status_code == 400

    def test_chat_history_valid(self, client, app):
        """获取对话历史 — 正常路径"""
        resp = client.get("/api/chat/fake-session-123/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert "get_chat_history" in app.dummy_api.invoked

    def test_chat_history_invalid_session(self, client):
        """获取对话历史 — 无效会话返回 404"""
        resp = client.get("/api/chat/bad-session/history")
        assert resp.status_code == 404
