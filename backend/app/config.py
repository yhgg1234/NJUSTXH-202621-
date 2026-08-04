"""
配置管理模块
从环境变量或 .env 文件中加载配置
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 优先读取根目录 .env，便于前后端和脚本共享同一份本地配置。
load_dotenv(BASE_DIR / ".env")


def _project_path(environment_name: str, default: Path) -> Path:
    configured = Path(os.getenv(environment_name, str(default)))
    return configured if configured.is_absolute() else BASE_DIR / configured


class Settings:
    """应用配置"""

    # 基础配置
    APP_NAME: str = "岗位能力图谱系统"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # 数据库配置
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4j123")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "root123")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "job_graph")

    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DATABASE: str = os.getenv("MONGO_DATABASE", "job_data")

    # 大模型配置
    LLM_API_URL: str = os.getenv(
        "LLM_API_URL",
        "https://spark-api-open.xf-yun.com/v1/chat/completions",
    )
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "lite")

    # 服务配置
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # 子任务 2.4：2.2 逐 JD 标准化数据与审核状态
    DISCOVERY_NORMALIZED_PATH: Path = _project_path(
        "DISCOVERY_NORMALIZED_PATH",
        BASE_DIR / "data" / "processed" / "normalized",
    )
    DISCOVERY_STATE_PATH: Path = _project_path(
        "DISCOVERY_STATE_PATH",
        BASE_DIR / "data" / "processed" / "discovery" / "state.json",
    )


settings = Settings()
