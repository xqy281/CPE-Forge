"""
空项目管线验证测试

验证在全新环境（空 attachments/ 和 output/）下，后台 API 链路不会崩溃，
所有端点返回合理的空结果。
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def empty_app(tmp_path):
    """创建一个指向空目录的 Flask 测试应用"""
    empty_attach = tmp_path / "attachments"
    empty_output = tmp_path / "output"
    empty_attach.mkdir()
    empty_output.mkdir()

    from web.app import create_app

    app = create_app()
    app.config["ATTACHMENTS_DIR"] = empty_attach
    app.config["OUTPUT_DIR"] = empty_output
    app.config["TESTING"] = True
    return app.test_client()


class TestEmptyProject:
    """模拟全新克隆后的空项目环境"""

    def test_employees_empty(self, empty_app):
        """空 attachments → 空员工列表"""
        r = empty_app.get("/api/employees")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_cleaning_report_not_found(self, empty_app):
        """无清洗报告文件 → 404"""
        r = empty_app.get("/api/cleaning-report")
        assert r.status_code == 404

    def test_analysis_status_empty(self, empty_app):
        """无员工 → 空分析状态"""
        r = empty_app.get("/api/analysis/status")
        assert r.status_code == 200
        assert r.get_json() == {}

    def test_analysis_all_empty(self, empty_app):
        """无员工 → 空聚合结果"""
        r = empty_app.get("/api/analysis/all")
        assert r.status_code == 200
        data = r.get_json()
        assert data["total_employees"] == 0
        assert data["analyzed_count"] == 0
        assert data["results"] == []

    def test_models_have_defaults(self, empty_app):
        """模型配置应有默认预设"""
        r = empty_app.get("/api/models")
        assert r.status_code == 200
        models = r.get_json()
        assert len(models) >= 7, f"默认预设数量不足: {len(models)}"

    def test_nonexist_employee_latest(self, empty_app):
        """不存在的员工 → 404"""
        r = empty_app.get("/api/analysis/nobody@test.com/latest")
        assert r.status_code == 404

    def test_nonexist_employee_history(self, empty_app):
        """不存在的员工 → 空历史"""
        r = empty_app.get("/api/analysis/nobody@test.com/history")
        assert r.status_code == 200
        assert r.get_json() == []
