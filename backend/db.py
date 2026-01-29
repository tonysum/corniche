from sqlalchemy import create_engine, text, inspect
from sqlalchemy.pool import QueuePool
import logging
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# 从配置文件获取数据库连接
try:
    from services.shared.config import DATABASE_URL
except ImportError:
    # 如果config模块不可用，使用环境变量构建连接URL
    PG_HOST = os.getenv("PG_HOST", "localhost")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_DB = os.getenv("PG_DB", "crypto_data")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "")
    
    if PG_PASSWORD:
        encoded_password = quote_plus(PG_PASSWORD)
        DATABASE_URL = f"postgresql://{PG_USER}:{encoded_password}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    else:
        DATABASE_URL = f"postgresql://{PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# 创建 PostgreSQL 数据库引擎
# 检查是否需要 SSL 连接
connect_args = {
    "connect_timeout": 10,  # 连接超时10秒
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5
}

# 如果环境变量要求 SSL，添加 SSL 参数
if os.getenv("PG_SSLMODE"):
    connect_args["sslmode"] = os.getenv("PG_SSLMODE")
elif "192.168" in DATABASE_URL or "localhost" not in DATABASE_URL.lower():
    # 对于远程连接，尝试使用 prefer SSL 模式
    # 如果服务器不支持 SSL，会自动降级到非 SSL
    connect_args["sslmode"] = "prefer"

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # 自动检测并重连断开的连接
    echo=False,
    connect_args=connect_args
)


# 1. 查询表是否存在，没有则创建
def create_table(table_name):
    """创建K线数据表（如果不存在）"""
    with engine.connect() as conn:
        # PostgreSQL 使用 information_schema 查询表是否存在
        # 注意：PostgreSQL中，如果表名用引号创建，会保持大小写；否则会转换为小写
        # 所以需要检查两种情况：原始大小写和小写
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND (table_name = :table_name OR table_name = LOWER(:table_name))
                );
            """),
            {"table_name": table_name}
        )
        
        table_exists = result.fetchone()[0]

        if not table_exists:
            # PostgreSQL 表创建语句
            # 注意：PostgreSQL 使用 DOUBLE PRECISION 而不是 REAL
            text_create = f"""
            CREATE TABLE "{table_name}" (
                trade_date VARCHAR(50) PRIMARY KEY,
                open_time BIGINT,
                open DOUBLE PRECISION,
                high DOUBLE PRECISION,
                low DOUBLE PRECISION,
                close DOUBLE PRECISION,
                volume DOUBLE PRECISION,
                close_time BIGINT,
                quote_volume DOUBLE PRECISION,
                trade_count INTEGER,
                active_buy_volume DOUBLE PRECISION,
                active_buy_quote_volume DOUBLE PRECISION,
                reserved_field TEXT,
                diff DOUBLE PRECISION,
                pct_chg DOUBLE PRECISION
            );
            """
            conn.execute(text(text_create))
            conn.commit()
            logging.info(f"Table '{table_name}' created successfully.")
        return table_exists
    
# 2. 删除表    
def delete_table(table_name):
    """删除指定的表"""
    with engine.connect() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}";'))
        conn.commit()
        logging.info(f"Table '{table_name}' deleted successfully.")


# 3. 创建交易记录表（用于回测结果存储）
def create_trade_table():
    """创建交易记录表"""
    table_name = 'backtrade_records'
    with engine.connect() as conn:
        # PostgreSQL 使用 information_schema 查询表是否存在
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = :table_name
                );
            """),
            {"table_name": table_name}
        )
        table_exists = result.fetchone()[0]
        
        if not table_exists:
            # PostgreSQL 表创建语句
            # 使用 BIGSERIAL 作为自增主键
            text_create = f"""
            CREATE TABLE "{table_name}" (
                id BIGSERIAL PRIMARY KEY,
                entry_date VARCHAR(50) NOT NULL,
                symbol VARCHAR(50) NOT NULL,
                entry_price DOUBLE PRECISION NOT NULL,
                entry_pct_chg DOUBLE PRECISION,
                position_size DOUBLE PRECISION NOT NULL,
                leverage INTEGER NOT NULL,
                exit_date VARCHAR(50),
                exit_price DOUBLE PRECISION,
                exit_reason TEXT,
                profit_loss DOUBLE PRECISION,
                profit_loss_pct DOUBLE PRECISION,
                max_profit DOUBLE PRECISION,
                max_loss DOUBLE PRECISION,
                hold_days INTEGER,
                has_added_position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            conn.execute(text(text_create))
            conn.commit()
            logging.info(f"交易记录表 '{table_name}' 创建成功")
        else:
            # 检查是否需要添加 has_added_position 字段
            # PostgreSQL 使用 information_schema.columns 查询列信息
            result = conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = :table_name;
                """),
                {"table_name": table_name}
            )
            columns = [row[0] for row in result.fetchall()]
            if 'has_added_position' not in columns:
                logging.info(f"添加 has_added_position 字段到表 '{table_name}'")
                conn.execute(
                    text(f'ALTER TABLE "{table_name}" ADD COLUMN has_added_position INTEGER DEFAULT 0;')
                )
                conn.commit()
            
            # 处理 hold_days 列：如果存在 hold_hours，迁移数据后删除；如果不存在 hold_days，添加它
            if 'hold_hours' in columns and 'hold_days' not in columns:
                logging.info(f"迁移 hold_hours 数据到 hold_days 字段")
                try:
                    # 先检查 hold_hours 列的数据类型
                    result = conn.execute(
                        text("""
                            SELECT data_type 
                            FROM information_schema.columns 
                            WHERE table_schema = 'public' 
                            AND table_name = :table_name 
                            AND column_name = 'hold_hours';
                        """),
                        {"table_name": table_name}
                    )
                    type_row = result.fetchone()
                    hold_hours_type = type_row[0] if type_row else None
                    
                    # 添加 hold_days 列
                    conn.execute(
                        text(f'ALTER TABLE "{table_name}" ADD COLUMN hold_days INTEGER;')
                    )
                    
                    # 根据 hold_hours 的数据类型进行不同的处理
                    if hold_hours_type in ('text', 'character varying', 'varchar'):
                        # 如果是文本类型，需要检查是否是有效的数字字符串
                        conn.execute(
                            text(f'''
                                UPDATE "{table_name}" 
                                SET hold_days = CASE 
                                    WHEN hold_hours IS NOT NULL 
                                        AND TRIM(hold_hours) != '' 
                                        AND hold_hours ~ '^[0-9]+$' 
                                    THEN (hold_hours::INTEGER) / 24 
                                    ELSE NULL 
                                END;
                            ''')
                        )
                    else:
                        # 如果是数字类型（INTEGER, BIGINT等），直接转换
                        conn.execute(
                            text(f'''
                                UPDATE "{table_name}" 
                                SET hold_days = CASE 
                                    WHEN hold_hours IS NOT NULL 
                                    THEN (hold_hours::INTEGER) / 24 
                                    ELSE NULL 
                                END;
                            ''')
                        )
                    conn.commit()
                    columns.append('hold_days')
                except Exception as e:
                    conn.rollback()
                    if 'already exists' not in str(e).lower() and 'duplicatecolumn' not in str(e).lower():
                        raise
                    logging.warning(f"列 hold_days 已存在，跳过添加")
                    # 重新查询列信息
                    result = conn.execute(
                        text("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_schema = 'public' 
                            AND table_name = :table_name;
                        """),
                        {"table_name": table_name}
                    )
                    columns = [row[0] for row in result.fetchall()]
                
                # 删除旧字段
                conn.execute(
                    text(f'ALTER TABLE "{table_name}" DROP COLUMN IF EXISTS hold_hours;')
                )
                conn.commit()
            elif 'hold_hours' in columns:
                # 如果两个字段都存在，只删除旧的
                logging.info(f"删除旧的 hold_hours 字段")
                conn.execute(
                    text(f'ALTER TABLE "{table_name}" DROP COLUMN IF EXISTS hold_hours;')
                )
                conn.commit()
            
            # 如果不存在 hold_days 列，添加它
            if 'hold_days' not in columns:
                logging.info(f"添加 hold_days 字段到表 '{table_name}'")
                try:
                    conn.execute(
                        text(f'ALTER TABLE "{table_name}" ADD COLUMN hold_days INTEGER;')
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    if 'already exists' not in str(e).lower() and 'duplicatecolumn' not in str(e).lower():
                        raise
                    logging.warning(f"列 hold_days 已存在，跳过添加")
            
            logging.info(f"交易记录表 '{table_name}' 已存在")
        
        return table_exists
