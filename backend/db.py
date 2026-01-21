import sqlite3
from sqlalchemy import create_engine, text
import logging

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
        # 🔧 修复：表名用双引号括起来，避免包含连字符等特殊字符时SQL语法错误
        result = conn.execute(
            text(f'SELECT name FROM sqlite_master WHERE type="table" AND name="{table_name}";')
        )
        
        table_exists = result.fetchone() is not None

        if not table_exists:
            # 🔧 修复：表名用双引号括起来，避免包含连字符等特殊字符时SQL语法错误
            text_create = f"""
            CREATE TABLE "{table_name}" (
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
            logging.info(f"Table '{table_name}' created successfully.")
        # 表已存在是正常情况，不需要输出日志，避免在批量下载时产生过多噪音
        return table_exists
    
# 2.删除表    
def delete_table(table_name):
    with engine.connect() as conn:
        # 🔧 修复：表名用双引号括起来，避免包含连字符等特殊字符时SQL语法错误
        conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}";'))
        logging.info(f"Table '{table_name}' deleted successfully.")


# 3.创建交易记录表（用于回测结果存储）
def create_trade_table():
    """创建交易记录表"""
    import logging
    table_name = 'backtrade_records'
    with engine.connect() as conn:
        # 🔧 修复：表名用双引号括起来，避免包含连字符等特殊字符时SQL语法错误
        result = conn.execute(
            text(f'SELECT name FROM sqlite_master WHERE type="table" AND name="{table_name}";')
        )
        table_exists = result.fetchone() is not None
        
        if not table_exists:
            # 🔧 修复：表名用双引号括起来，避免包含连字符等特殊字符时SQL语法错误
            text_create = f"""
            CREATE TABLE "{table_name}" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                entry_pct_chg REAL,
                position_size REAL NOT NULL,
                leverage INTEGER NOT NULL,
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                profit_loss REAL,
                profit_loss_pct REAL,
                max_profit REAL,
                max_loss REAL,
                hold_hours INTEGER,
                has_added_position INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
            conn.execute(text(text_create))
            conn.commit()
            logging.info(f"交易记录表 '{table_name}' 创建成功")
        else:
            # 检查是否需要添加has_added_position字段
            # 🔧 修复：表名用双引号括起来，避免包含连字符等特殊字符时SQL语法错误
            result = conn.execute(
                text(f'PRAGMA table_info("{table_name}");')
            )
            columns = [row[1] for row in result.fetchall()]
            if 'has_added_position' not in columns:
                logging.info(f"添加 has_added_position 字段到表 '{table_name}'")
                # 🔧 修复：表名用双引号括起来，避免包含连字符等特殊字符时SQL语法错误
                conn.execute(
                    text(f'ALTER TABLE "{table_name}" ADD COLUMN has_added_position INTEGER DEFAULT 0;')
                )
                conn.commit()
            logging.info(f"交易记录表 '{table_name}' 已存在")
        
        return table_exists
