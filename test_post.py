import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# PostgreSQL 连接配置
DB_HOST = os.getenv("DB_HOST", "192.168.2.200")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "crypto_data")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "891109")

# 构建连接字符串
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 创建引擎（使用连接池）
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 自动重连
    echo=False
)

with engine.connect() as conn:
    result = conn.execute(text("SELECT 1"))
    print(result.all())