"""
共享配置
"""
import os
from pathlib import Path

# 项目根目录（backend目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 数据库路径（默认在项目根目录的data目录，或通过环境变量指定）
# 在Docker容器中，DB_PATH会通过环境变量设置
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT.parent / "data" / "crypto_data.db"))

# 服务端口配置
DATA_SERVICE_PORT = int(os.getenv("DATA_SERVICE_PORT", "8001"))
BACKTEST_SERVICE_PORT = int(os.getenv("BACKTEST_SERVICE_PORT", "8002"))
ORDER_SERVICE_PORT = int(os.getenv("ORDER_SERVICE_PORT", "8003"))

# CORS配置
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

