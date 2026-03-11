"""
RESTful API 蓝图 — 将 pipeline/api.py 的方法映射为 HTTP 端点。

所有端点以 /api 为前缀（由 app.py 注册时指定）。
"""
import json
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app
from pipeline.api import CPEPipelineAPI
from pipeline.llm_config import (
    list_model_configs,
    load_model_config,
    update_model_config,
)

logger = logging.getLogger(__name__)

# 创建 API 蓝图
api_bp = Blueprint("api", __name__)


def get_pipeline() -> CPEPipelineAPI:
    """延迟实例化管线 API（需要 Flask 应用上下文）"""
    return CPEPipelineAPI(
        attachments_dir=current_app.config["ATTACHMENTS_DIR"],
        output_dir=current_app.config["OUTPUT_DIR"],
    )


def _check_api_key(model_id: str) -> str | None:
    """检查指定模型是否已配置 API Key，未配置则返回错误信息"""
    cfg = load_model_config(model_id)
    if cfg and not cfg.api_key:
        return f"模型 [{cfg.display_name or model_id}] 尚未配置 API Key，请先在「模型配置」页面设置"
    return None


# =============================================================================
# GET 端点
# =============================================================================

@api_bp.route("/cleaning-report", methods=["GET"])
def get_cleaning_report():
    """获取数据清洗报告 — 从 output/cleaning_report.json 读取并增强"""
    try:
        report_path = Path(current_app.config["OUTPUT_DIR"]) / "cleaning_report.json"
        if not report_path.exists():
            return jsonify({"error": "清洗报告文件不存在，请先执行数据清洗管线"}), 404

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        # 员工邮箱 → 中文名映射（从 attachments 目录获取）
        api = get_pipeline()
        emp_list = api.get_employee_list()
        name_map = {e["email"]: e["name"] for e in emp_list}

        # 增强员工明细：添加中文名
        employee_detail = report.get("员工明细", {})
        enhanced_employees = []
        for email, count in employee_detail.items():
            enhanced_employees.append({
                "email": email,
                "name": name_map.get(email, email.split("@")[0]),
                "report_count": count,
            })
        # 按周报数降序排列
        enhanced_employees.sort(key=lambda x: x["report_count"], reverse=True)

        # 按员工分组加密文件
        encrypted_files = report.get("加密文件清单", [])
        encrypted_by_employee = {}
        for fpath in encrypted_files:
            # 路径格式: attachments\\email\\filename.xlsx
            parts = fpath.replace("\\\\", "\\").split("\\")
            if len(parts) >= 2:
                emp_email = parts[1] if parts[0] == "attachments" else parts[0]
                if emp_email not in encrypted_by_employee:
                    encrypted_by_employee[emp_email] = []
                encrypted_by_employee[emp_email].append(parts[-1])

        return jsonify({
            "total_files": report.get("总文件数", 0),
            "valid_files": report.get("有效文件", 0),
            "filtered_files": report.get("被过滤文件", 0),
            "encrypted_files": report.get("加密文件", 0),
            "corrupted_files": report.get("损坏文件", 0),
            "total_sheets": report.get("Sheet总数", 0),
            "deduplicated_sheets": report.get("去重后Sheet数", 0),
            "duplicate_groups": report.get("重复组数", 0),
            "dedup_rate": report.get("去重率", "0%"),
            "employees": enhanced_employees,
            "encrypted_by_employee": encrypted_by_employee,
        })
    except Exception as e:
        logger.error("获取清洗报告失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/employees", methods=["GET"])
def get_employees():
    """获取所有可用员工列表"""
    try:
        api = get_pipeline()
        employees = api.get_employee_list()
        return jsonify(employees)
    except Exception as e:
        logger.error("获取员工列表失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/employees/<string:email>/ranges", methods=["GET"])
def get_ranges(email: str):
    """获取指定员工可用的周报时间范围列表"""
    try:
        api = get_pipeline()
        ranges = api.get_employee_report_ranges(email)
        return jsonify(ranges)
    except Exception as e:
        logger.error("获取时间范围失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---- 模型配置 CRUD ----

@api_bp.route("/models", methods=["GET"])
def get_models():
    """获取所有已配置的 LLM 模型列表（含脱敏 key 和参数）"""
    try:
        configs = list_model_configs(enabled_only=False)
        return jsonify([c.to_safe_dict() for c in configs])
    except Exception as e:
        logger.error("获取模型列表失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/models/<path:model_id>", methods=["GET"])
def get_model_detail(model_id: str):
    """获取单个模型完整配置（api_key 脱敏）"""
    try:
        cfg = load_model_config(model_id)
        if not cfg:
            return jsonify({"error": f"模型 {model_id} 不存在"}), 404
        return jsonify(cfg.to_safe_dict())
    except Exception as e:
        logger.error("获取模型详情失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/models/<path:model_id>", methods=["PUT"])
def update_model(model_id: str):
    """更新模型配置（api_key, temperature, top_p 等）"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    try:
        updated = update_model_config(model_id, data)
        if not updated:
            return jsonify({"error": f"模型 {model_id} 不存在"}), 404
        return jsonify(updated.to_safe_dict())
    except Exception as e:
        logger.error("更新模型配置失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ---- 分析结果 ----

@api_bp.route("/analysis/<string:email>/latest", methods=["GET"])
def get_latest_analysis(email: str):
    """读取指定员工最近一次的分析结果缓存"""
    try:
        api = get_pipeline()
        result = api.get_analysis_result(email)
        if result:
            return jsonify(result.to_web_response())
        return jsonify({"error": "未找到缓存的分析结果"}), 404
    except Exception as e:
        logger.error("读取分析结果失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/analysis/<string:email>/file/<string:filename>", methods=["GET"])
def get_analysis_by_file(email: str, filename: str):
    """根据文件名读取指定的历史分析结果"""
    try:
        output_dir = Path(current_app.config["OUTPUT_DIR"]) / email
        filepath = output_dir / filename

        # 安全检查：防止路径遍历
        if not filepath.resolve().is_relative_to(output_dir.resolve()):
            return jsonify({"error": "非法文件路径"}), 403

        if not filepath.exists():
            return jsonify({"error": f"文件 {filename} 不存在"}), 404

        data = json.loads(filepath.read_text(encoding="utf-8"))
        return jsonify(data)
    except Exception as e:
        logger.error("读取历史分析文件失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/analysis/<string:email>/history", methods=["GET"])
def get_analysis_history(email: str):
    """列出指定员工所有历史分析结果文件"""
    try:
        output_dir = Path(current_app.config["OUTPUT_DIR"]) / email
        if not output_dir.exists():
            return jsonify([])

        history = []
        for f in sorted(output_dir.glob("*_analysis.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                history.append({
                    "filename": f.name,
                    "generated_at": data.get("generated_at", ""),
                    "model_id": data.get("model_id", "unknown"),
                    "date_range_ids": data.get("date_range_ids", []),
                    "date_range_count": len(data.get("date_range_ids", [])),
                    "elapsed_seconds": data.get("elapsed_seconds", 0),
                })
            except Exception:
                continue

        return jsonify(history)
    except Exception as e:
        logger.error("查询分析历史失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/analysis/status", methods=["GET"])
def get_analysis_status():
    """批量查询所有员工的分析缓存状态"""
    try:
        api = get_pipeline()
        employees = api.get_employee_list()
        output_dir = Path(current_app.config["OUTPUT_DIR"])
        
        status = {}
        for emp in employees:
            email = emp["email"]
            emp_dir = output_dir / email
            has_cache = emp_dir.exists() and any(emp_dir.glob("*_analysis.json"))
            status[email] = has_cache
        
        return jsonify(status)
    except Exception as e:
        logger.error("查询分析状态失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/analysis/all", methods=["GET"])
def get_all_analysis():
    """聚合所有已分析员工的结果（团队大盘用）— 优先选取覆盖范围最广的报告"""
    try:
        api = get_pipeline()
        employees = api.get_employee_list()
        results = []
        
        for emp in employees:
            result = api.get_widest_analysis_result(emp["email"])
            if result:
                results.append(result.to_web_response())
        
        return jsonify({
            "total_employees": len(employees),
            "analyzed_count": len(results),
            "results": results,
        })
    except Exception as e:
        logger.error("聚合分析失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# =============================================================================
# POST 端点（操作触发）
# =============================================================================

@api_bp.route("/estimate-tokens", methods=["POST"])
def estimate_tokens():
    """Token 预估 — 在触发 LLM 之前预检资源消耗"""
    data = request.get_json(silent=True)
    if not data or "email" not in data or "range_ids" not in data:
        return jsonify({"error": "缺少必填字段: email, range_ids"}), 400

    try:
        api = get_pipeline()
        estimate = api.estimate_tokens(
            email=data["email"],
            date_range_ids=data["range_ids"],
            model=data.get("model_id", "deepseek/deepseek-chat"),
        )
        return jsonify(estimate)
    except Exception as e:
        logger.error("Token 预估失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/analysis/full", methods=["POST"])
def run_full_analysis():
    """触发完整 LLM 分析（画像提取 + 成长分析）"""
    data = request.get_json(silent=True)
    if not data or not all(k in data for k in ("email", "range_ids", "model_id")):
        return jsonify({"error": "缺少必填字段: email, range_ids, model_id"}), 400

    # 前置校验 API Key
    key_err = _check_api_key(data["model_id"])
    if key_err:
        return jsonify({"error": key_err, "need_config": True}), 400

    try:
        api = get_pipeline()
        result = api.run_full_analysis(
            email=data["email"],
            date_range_ids=data["range_ids"],
            model_id=data["model_id"],
        )
        return jsonify(result.to_web_response())
    except Exception as e:
        logger.error("完整分析失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/analysis/profile", methods=["POST"])
def run_profile_only():
    """仅触发双层能力画像提取"""
    data = request.get_json(silent=True)
    if not data or not all(k in data for k in ("email", "range_ids", "model_id")):
        return jsonify({"error": "缺少必填字段: email, range_ids, model_id"}), 400

    key_err = _check_api_key(data["model_id"])
    if key_err:
        return jsonify({"error": key_err, "need_config": True}), 400

    try:
        api = get_pipeline()
        result = api.run_profile_only(
            email=data["email"],
            date_range_ids=data["range_ids"],
            model_id=data["model_id"],
        )
        return jsonify(result)
    except Exception as e:
        logger.error("画像提取失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/analysis/growth", methods=["POST"])
def run_growth_only():
    """仅触发成长时间轴分析"""
    data = request.get_json(silent=True)
    if not data or not all(k in data for k in ("email", "range_ids", "model_id")):
        return jsonify({"error": "缺少必填字段: email, range_ids, model_id"}), 400

    key_err = _check_api_key(data["model_id"])
    if key_err:
        return jsonify({"error": key_err, "need_config": True}), 400

    try:
        api = get_pipeline()
        result = api.run_growth_only(
            email=data["email"],
            date_range_ids=data["range_ids"],
            model_id=data["model_id"],
        )
        return jsonify(result)
    except Exception as e:
        logger.error("成长分析失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# =============================================================================
# FAQ 对话端点
# =============================================================================

@api_bp.route("/chat/start", methods=["POST"])
def chat_start():
    """创建 FAQ 对话会话"""
    data = request.get_json(silent=True)
    if not data or not all(k in data for k in ("email", "range_ids", "model_id")):
        return jsonify({"error": "缺少必填字段: email, range_ids, model_id"}), 400

    key_err = _check_api_key(data["model_id"])
    if key_err:
        return jsonify({"error": key_err, "need_config": True}), 400

    try:
        api = get_pipeline()
        session_id = api.start_chat_session(
            email=data["email"],
            date_range_ids=data["range_ids"],
            model_id=data["model_id"],
        )
        return jsonify({"session_id": session_id})
    except Exception as e:
        logger.error("创建对话会话失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/chat/send", methods=["POST"])
def chat_send():
    """向指定对话会话发送消息"""
    data = request.get_json(silent=True)
    if not data or not all(k in data for k in ("session_id", "message")):
        return jsonify({"error": "缺少必填字段: session_id, message"}), 400

    try:
        api = get_pipeline()
        reply = api.chat(session_id=data["session_id"], message=data["message"])
        return jsonify(reply)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error("发送消息失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/chat/<string:session_id>/history", methods=["GET"])
def chat_history(session_id: str):
    """获取指定对话会话的完整历史"""
    try:
        api = get_pipeline()
        history = api.get_chat_history(session_id)
        return jsonify(history)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error("获取对话历史失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500
