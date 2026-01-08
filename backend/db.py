import sqlite3
from sqlalchemy import create_engine, text

# 0. 建立数据库连接
# 数据库文件路径（使用相对路径，兼容Docker环境）
import os
from pathlib import Path

# 获取数据库路径：优先使用环境变量，否则使用项目根目录下的 data/crypto_data.db
db_path = os.getenv("DB_PATH")
if not db_path:
    # backend目录的父目录（项目根目录）下的 data/crypto_data.db
    backend_dir = Path(__file__).parent
    project_root = backend_dir.parent
    db_path = str(project_root / "data" / "crypto_data.db")

# 确保数据库目录存在
db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

engine = create_engine(f'sqlite:///{db_path}')


# 1.查询表是否存在,没有则创建
def create_table(table_name):
    with engine.connect() as conn:
        
        result = conn.execute(
            text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        )
        
        table_exists = result.fetchone() is not None

        if not table_exists:
            text_create = f"""
            CREATE TABLE {table_name} (
                trade_date TEXT,
                open_time REAL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                close_time REAL,
                quote_volume REAL,
                trade_count INTEGER,
                active_buy_volume REAL,
                active_buy_quote_volume REAL,
                reserved_field TEXT,
                diff REAL,
                pct_chg REAL,
                PRIMARY KEY (trade_date)               
            );
            """
            conn.execute(text(text_create))
            print(f"Table '{table_name}' created successfully.")
        else:
            print(f"Table '{table_name}' already exists.")
        return table_exists
    
# 2.删除表    
def delete_table(table_name):
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name};"))
        print(f"Table '{table_name}' deleted successfully.")
