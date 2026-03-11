"""
CPE-Forge Web 后端入口

Flask 应用工厂，注册 API Blueprint，提供 RESTful 端点。
前端由 Vite 开发服务器（:5173）代理到本后端（:5000）。
"""
import logging
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from web.api_routes import api_bp
from pipeline.llm_config import init_default_configs

# -----------------------------------------------------------------------------
# 项目路径
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
ATTACHMENTS_DIR = BASE_DIR / "attachments"
OUTPUT_DIR = BASE_DIR / "output"

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 应用工厂
# -----------------------------------------------------------------------------
def create_app() -> Flask:
    """
    创建并配置 Flask 应用。

    职责：
    1. 注册 /api Blueprint（全部端点由 api_routes.py 定义）
    2. 启用 CORS（开发模式下 Vite :5173 跨域访问 :5000）
    3. 确保模型默认配置文件存在
    """
    app = Flask(__name__)

    # 开发模式允许跨域（Vite dev server）
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册 API 蓝图
    app.register_blueprint(api_bp, url_prefix="/api")

    # 注入路径配置供 Blueprint 使用
    app.config["ATTACHMENTS_DIR"] = ATTACHMENTS_DIR
    app.config["OUTPUT_DIR"] = OUTPUT_DIR

    # 首次启动时初始化默认模型配置（幂等，不覆盖已有配置）
    init_default_configs()

    return app


if __name__ == "__main__":
    app = create_app()
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"启动 Web API — Attachments: {ATTACHMENTS_DIR}, Output: {OUTPUT_DIR}")

    # 监听所有接口，端口 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
