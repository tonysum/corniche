# SQLite 到 PostgreSQL 数据迁移指南

## 📋 概述

本指南介绍如何将 SQLite 数据库中的数据迁移到 PostgreSQL 服务器。

## 🔧 前置条件

### 1. 安装 PostgreSQL

#### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

#### 使用 Docker（推荐）
```bash
docker run --name postgres-crypto \
  -e POSTGRES_DB=crypto_data \
  -e POSTGRES_USER=crypto_user \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  -d postgres:15
```

### 2. 创建数据库和用户

```bash
# 连接到 PostgreSQL
psql -U postgres

# 创建数据库
CREATE DATABASE crypto_data;

# 创建用户（如果使用 Docker，用户已自动创建）
CREATE USER crypto_user WITH PASSWORD 'your_password';

# 授予权限
GRANT ALL PRIVILEGES ON DATABASE crypto_data TO crypto_user;

# 连接到新数据库并授予 schema 权限
\c crypto_data
GRANT ALL ON SCHEMA public TO crypto_user;
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

确保安装了以下依赖：
- `pandas`
- `sqlalchemy`
- `psycopg2-binary`（PostgreSQL 驱动）
- `python-dotenv`

## 🚀 使用方法

### 方式1：使用命令行参数（推荐用于一次性迁移）

```bash
python migrate.py \
  --sqlite-path data/crypto_data.db \
  --pg-host localhost \
  --pg-port 5432 \
  --pg-db crypto_data \
  --pg-user crypto_user \
  --pg-password your_password
```

### 方式2：使用环境变量（推荐用于重复使用）

1. 在 `.env` 文件中配置 PostgreSQL 连接信息：

```env
PG_HOST=localhost
PG_PORT=5432
PG_DB=crypto_data
PG_USER=crypto_user
PG_PASSWORD=your_password
```

2. 运行迁移脚本：

```bash
python migrate.py
```

### 方式3：只迁移特定类型的表

```bash
# 只迁移日线表（K1d开头）
python migrate.py --table-filter K1d

# 只迁移5分钟表（K5m开头）
python migrate.py --table-filter K5m

# 只迁移小时线表（K1h开头）
python migrate.py --table-filter K1h
```

### 方式4：自定义批量大小

```bash
# 使用更大的批量大小（适合大表）
python migrate.py --batch-size 50000
```

## 📊 迁移过程

### 迁移步骤

1. **连接数据库**
   - 连接到 SQLite 源数据库
   - 连接到 PostgreSQL 目标数据库

2. **获取表列表**
   - 扫描 SQLite 数据库中的所有表
   - 支持过滤特定类型的表

3. **创建表结构**
   - 读取每个表的架构信息
   - 在 PostgreSQL 中创建对应的表
   - 自动转换数据类型（SQLite → PostgreSQL）

4. **迁移数据**
   - 分批读取 SQLite 数据
   - 批量插入到 PostgreSQL
   - 显示迁移进度

5. **验证结果**
   - 统计迁移的表数和行数
   - 报告成功和失败的表

### 数据类型映射

| SQLite 类型 | PostgreSQL 类型 |
|------------|----------------|
| INTEGER    | BIGINT         |
| REAL       | DOUBLE PRECISION |
| TEXT       | TEXT           |
| BLOB       | BYTEA          |
| NUMERIC    | NUMERIC        |

### 表名处理

- PostgreSQL 对表名大小写敏感
- 使用双引号包裹表名以保持原始大小写
- 例如：`K1dBTCUSDT` → `"K1dBTCUSDT"`

## ⚙️ 高级选项

### 跳过已存在的表

默认情况下，如果表已存在且有数据，会跳过迁移：

```bash
python migrate.py  # 默认跳过已存在的表
```

### 强制重新迁移

```bash
python migrate.py --no-skip-existing  # 重新迁移所有表
```

### 指定 SQLite 数据库路径

```bash
python migrate.py --sqlite-path /path/to/other/database.db
```

## 🔍 故障排查

### 1. 连接失败

**错误**：`无法连接到 PostgreSQL`

**解决方案**：
- 检查 PostgreSQL 服务是否运行：`brew services list | grep postgresql`（macOS）
- 检查端口是否正确：`lsof -i :5432`
- 检查用户名和密码是否正确
- 检查防火墙设置

### 2. 权限错误

**错误**：`permission denied`

**解决方案**：
```sql
-- 授予用户所有权限
GRANT ALL PRIVILEGES ON DATABASE crypto_data TO crypto_user;
\c crypto_data
GRANT ALL ON SCHEMA public TO crypto_user;
```

### 3. 表已存在错误

**错误**：`relation "xxx" already exists`

**解决方案**：
- 使用 `--no-skip-existing` 强制重新迁移
- 或手动删除表：`DROP TABLE "table_name";`

### 4. 内存不足

**错误**：内存使用过高

**解决方案**：
- 减小批量大小：`--batch-size 5000`
- 分批迁移不同类型的表

### 5. 数据类型错误

**错误**：`column "xxx" is of type xxx but expression is of type xxx`

**解决方案**：
- 检查源表的数据类型
- 可能需要手动调整数据类型映射

## 📈 性能优化

### 1. 批量大小调整

根据表大小调整批量大小：
- 小表（< 10万行）：`--batch-size 10000`
- 中表（10-100万行）：`--batch-size 50000`
- 大表（> 100万行）：`--batch-size 100000`

### 2. 并行迁移

可以同时运行多个迁移进程，迁移不同类型的表：

```bash
# 终端1：迁移日线表
python migrate.py --table-filter K1d

# 终端2：迁移小时线表
python migrate.py --table-filter K1h

# 终端3：迁移5分钟表
python migrate.py --table-filter K5m
```

### 3. PostgreSQL 优化

在迁移前优化 PostgreSQL 配置：

```sql
-- 禁用自动提交（提高性能）
SET synchronous_commit = OFF;

-- 增加 work_mem（提高排序性能）
SET work_mem = '256MB';

-- 迁移完成后恢复
SET synchronous_commit = ON;
```

## 📝 迁移后验证

### 1. 检查表数量

```sql
-- 在 PostgreSQL 中
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name LIKE 'K%';
```

### 2. 检查数据行数

```sql
-- 比较 SQLite 和 PostgreSQL 的行数
-- SQLite
SELECT COUNT(*) FROM "K1dBTCUSDT";

-- PostgreSQL
SELECT COUNT(*) FROM "K1dBTCUSDT";
```

### 3. 抽样验证

```sql
-- 随机抽样几条数据对比
SELECT * FROM "K1dBTCUSDT" ORDER BY RANDOM() LIMIT 10;
```

## 🔄 迁移后操作

### 1. 更新应用配置

修改 `db.py` 或创建 `db_postgres.py`，使用 PostgreSQL 连接。

### 2. 创建索引（可选）

```sql
-- 为常用查询字段创建索引
CREATE INDEX idx_trade_date ON "K1dBTCUSDT" (trade_date);
CREATE INDEX idx_symbol_trade_date ON "K1dBTCUSDT" (symbol, trade_date);
```

### 3. 更新应用代码

将所有使用 SQLite 的代码改为使用 PostgreSQL。

## 📚 相关文档

- [数据库迁移分析.md](../数据库迁移分析.md)
- [PostgreSQL检测方法.md](../PostgreSQL检测方法.md)

## ⚠️ 注意事项

1. **备份数据**：迁移前务必备份 SQLite 数据库
2. **磁盘空间**：确保 PostgreSQL 服务器有足够的磁盘空间
3. **网络稳定**：如果 PostgreSQL 在远程服务器，确保网络连接稳定
4. **迁移时间**：大型数据库迁移可能需要数小时，请合理安排时间
5. **验证数据**：迁移完成后务必验证数据完整性

## 🆘 获取帮助

如果遇到问题，请检查：
1. 日志输出中的错误信息
2. PostgreSQL 日志文件
3. 数据库连接配置
