# PostgreSQL 迁移说明

## ✅ 已完成的修改

### 核心数据库模块

1. **`backend/db.py`** ✅
   - 完全改为 PostgreSQL 连接
   - 使用 `DATABASE_URL` 从配置读取
   - 添加 SSL 连接支持
   - 更新所有表创建和查询逻辑

2. **`backend/services/shared/config.py`** ✅
   - 添加 PostgreSQL 配置参数
   - 构建 `DATABASE_URL`
   - 添加 `.env` 文件加载支持

### 数据管理模块

3. **`backend/data.py`** ✅
   - 更新 `get_local_symbols()` - 使用 `information_schema.tables`
   - 更新 `delete_all_tables()` - 使用 `information_schema.tables`
   - 更新 `delete_kline_data()` - 使用 `information_schema.tables`

4. **`backend/download_klines.py`** ✅
   - 更新 `get_local_symbols()` - 使用 `information_schema.tables`

### 回测模块

5. **`backend/backtrade.py`** ✅
   - 更新 `create_trade_table()` - 改为 PostgreSQL 语法
   - 简化字段添加逻辑

6. **`backend/backtrade1d.py`** ✅
   - 更新 `create_trade_table()` - 使用 `db.create_trade_table()`

7. **`backend/smartmoney.py`** ✅
   - 更新 `create_trade_table()` - 使用 `db.create_trade_table()`

8. **`backend/backtrade4.py`** ✅
   - 已导入 `create_trade_table`，无需修改

### 配置文件

9. **`.env.example`** ✅
   - 创建 PostgreSQL 配置模板

## ⚠️ 需要手动更新的文件

以下文件直接使用 `sqlite3` 连接，需要更新为使用 `db.py` 的 engine：

### 回测策略文件

- **`backend/hm1.py`** ⚠️ 部分更新
  - 已更新：`__init__` 方法改为使用 `engine`
  - 已更新：部分查询改为使用 SQLAlchemy
  - **需要更新**：仍有多个地方使用 `cursor.execute()`，需要改为使用 `engine.connect()`

- **`backend/hm1new.py`** ⚠️ 需要更新
- **`backend/hm1-nan.py`** ⚠️ 需要更新
- **`backend/hm1-old.py`** ⚠️ 需要更新
- **`backend/hm5.py`** ⚠️ 需要更新
- **`backend/hm500.py`** ⚠️ 需要更新
- **`backend/hm20260121.py`** ⚠️ 需要更新

### 迁移工具

- **`backend/migrate.py`** ⚠️ 特殊处理
  - 这个文件用于 SQLite → PostgreSQL 迁移
  - 需要保留 SQLite 连接功能
  - 只需要确保目标 PostgreSQL 连接正确

## 🔧 更新模式

### 模式1: 替换 sqlite3 连接

**之前：**
```python
import sqlite3
self.crypto_conn = sqlite3.connect(DB_PATH)
cursor = self.crypto_conn.cursor()
cursor.execute("SELECT ...")
result = cursor.fetchone()
```

**之后：**
```python
from db import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SELECT ..."), {"param": value})
    row = result.fetchone()
```

### 模式2: 替换表查询

**之前：**
```python
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'K1d%'")
tables = cursor.fetchall()
```

**之后：**
```python
result = conn.execute(text("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE :prefix
"""), {"prefix": "K1d%"})
tables = result.fetchall()
```

### 模式3: 替换参数化查询

**之前（SQLite）：**
```python
cursor.execute("SELECT * FROM table WHERE col = ?", (value,))
```

**之后（PostgreSQL）：**
```python
conn.execute(text("SELECT * FROM table WHERE col = :value"), {"value": value})
```

## 📝 环境变量配置

创建 `.env` 文件：

```env
# PostgreSQL 数据库配置
PG_HOST=192.168.2.200
PG_PORT=5432
PG_DB=crypto_data
PG_USER=postgres
PG_PASSWORD=your_password_here

# SSL 模式（可选）
PG_SSLMODE=prefer

# 服务端口配置
BACKTEST_SERVICE_PORT=8002
ORDER_SERVICE_PORT=8003
```

## ✅ 验证步骤

1. **测试数据库连接**
   ```bash
   python test_post.py
   ```

2. **测试核心功能**
   ```bash
   # 测试数据查询
   python -c "from backend.data import get_local_symbols; print(get_local_symbols('1d'))"
   
   # 测试表创建
   python -c "from backend.db import create_table; create_table('K1dTESTUSDT')"
   ```

3. **启动服务**
   ```bash
   cd backend
   python services/backtest_service/main.py
   ```

## 🔍 常见问题

### 问题1: 连接失败

**错误：** `connection refused` 或 `host is down`

**解决：**
1. 检查 PostgreSQL 服务是否运行
2. 检查 `.env` 文件中的配置
3. 检查防火墙设置

### 问题2: 表不存在

**错误：** `relation "table_name" does not exist`

**解决：**
1. 确保表已创建（使用 `create_table()` 函数）
2. 检查表名大小写（PostgreSQL 区分大小写）

### 问题3: 数据类型错误

**错误：** `column "col" is of type double precision but expression is of type real`

**解决：**
- 确保使用 `DOUBLE PRECISION` 而不是 `REAL`
- 检查表创建语句

## 📚 相关文档

- [PostgreSQL迁移完成.md](./PostgreSQL迁移完成.md) - 详细迁移报告
- [PostgreSQL安装说明.md](./PostgreSQL安装说明.md)
- [PostgreSQL连接问题解决.md](./PostgreSQL连接问题解决.md)
