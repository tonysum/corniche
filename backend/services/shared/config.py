"""
共享配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote_plus

# 加载 .env 文件
backend_dir = Path(__file__).parent.parent.parent
project_root = backend_dir.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# 项目根目录（backend目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent

# PostgreSQL 数据库配置
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "crypto_data")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")

# 数据库连接URL
# 对密码进行 URL 编码以处理特殊字符
if PG_PASSWORD:
    encoded_password = quote_plus(PG_PASSWORD)
    DATABASE_URL = f"postgresql://{PG_USER}:{encoded_password}@{PG_HOST}:{PG_PORT}/{PG_DB}"
else:
    DATABASE_URL = f"postgresql://{PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# SSL 模式配置（如果需要）
PG_SSLMODE = os.getenv("PG_SSLMODE", "")  # 可选值: disable, allow, prefer, require, verify-ca, verify-full

# 保持向后兼容（已废弃，使用 DATABASE_URL）
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT.parent / "data" / "crypto_data.db"))

# 服务端口配置
BACKTEST_SERVICE_PORT = int(os.getenv("BACKTEST_SERVICE_PORT", "8002"))
ORDER_SERVICE_PORT = int(os.getenv("ORDER_SERVICE_PORT", "8003"))

# CORS配置
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3002",  # 回测交易前端
    "http://127.0.0.1:3002",
    # 服务器 IP（用于远程访问）
    "http://8.216.33.6:3002",  # 回测交易前端（服务器）
    # 本地网络访问
    "http://192.168.2.103:3002",  # 本地网络回测交易前端
    "http://192.168.2.103:3000",  # 本地网络数据管理前端
    # 如果需要 HTTPS，可以添加：
    # "https://8.216.33.6:3001",
    # "https://8.216.33.6:3002",
]

