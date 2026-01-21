# 数据迁移快速开始指南

## 🚀 5分钟快速开始

### 步骤1：安装 PostgreSQL（如果还没有）

#### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
```

#### Docker（最简单）
```bash
docker run --name postgres-crypto \
  -e POSTGRES_DB=crypto_data \
  -e POSTGRES_USER=crypto_user \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  -d postgres:15
```

### 步骤2：创建数据库（如果使用 Docker，可跳过）

```bash
psql -U postgres

CREATE DATABASE crypto_data;
CREATE USER crypto_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE crypto_data TO crypto_user;
\c crypto_data
GRANT ALL ON SCHEMA public TO crypto_user;
\q
```

### 步骤3：安装依赖

```bash
pip install psycopg2-binary
```

### 步骤4：配置 .env 文件（推荐）

在项目根目录的 `.env` 文件中添加 PostgreSQL 配置：

```env
# PostgreSQL 数据库配置
PG_HOST=localhost
PG_PORT=5432
PG_DB=crypto_data
PG_USER=crypto_user
PG_PASSWORD=your_password

# SQLite 数据库路径（可选，默认: data/crypto_data.db）
# SQLITE_PATH=data/crypto_data.db
```

### 步骤5：运行迁移

```bash
# 方式1：使用 .env 文件（推荐，最简单）
python migrate.py

# 方式2：使用命令行参数覆盖 .env 配置
python migrate.py --pg-password different_password

# 方式3：完全使用命令行参数（不使用 .env）
python migrate.py \
  --pg-host localhost \
  --pg-port 5432 \
  --pg-db crypto_data \
  --pg-user crypto_user \
  --pg-password your_password
```

**配置优先级**：命令行参数 > .env 文件 > 默认值

## 📊 迁移进度

迁移脚本会显示：
- ✅ 成功创建的表
- ✅ 成功迁移的行数
- ⏭️  跳过的表（已存在）
- ❌ 失败的表和错误信息

## 🎯 常见使用场景

### 1. 迁移所有数据

```bash
python migrate.py
```

### 2. 只迁移日线数据

```bash
python migrate.py --table-filter K1d
```

### 3. 只迁移5分钟数据

```bash
python migrate.py --table-filter K5m
```

### 4. 迁移大表（调整批量大小）

```bash
python migrate.py --batch-size 50000
```

## ⚠️ 注意事项

1. **首次迁移**：建议先用 `--table-filter` 测试一个小表
2. **磁盘空间**：确保 PostgreSQL 有足够空间（至少是 SQLite 数据库的 1.5 倍）
3. **迁移时间**：大型数据库可能需要数小时
4. **网络稳定**：如果 PostgreSQL 在远程，确保网络稳定

## 🔍 验证迁移结果

```bash
# 连接到 PostgreSQL
psql -U crypto_user -d crypto_data

# 查看表数量
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name LIKE 'K%';

# 查看某个表的数据量
SELECT COUNT(*) FROM "K1dBTCUSDT";
```

## 📚 更多信息

详细文档请参考：[README_MIGRATION.md](README_MIGRATION.md)
