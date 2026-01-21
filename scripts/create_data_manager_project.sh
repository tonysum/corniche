#!/bin/bash

# 数据管理模块独立项目创建脚本
# 用法: ./scripts/create_data_manager_project.sh [目标目录]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# 目标目录
TARGET_DIR="${1:-$PROJECT_ROOT/../crypto-data-manager}"

echo -e "${GREEN}开始创建数据管理独立项目...${NC}"
echo -e "源项目: ${PROJECT_ROOT}"
echo -e "目标目录: ${TARGET_DIR}"
echo ""

# 创建目录结构
echo -e "${YELLOW}创建目录结构...${NC}"
mkdir -p "$TARGET_DIR"/{backend,frontend/{app,components,contexts,lib},data,scripts,docs}

# 复制后端文件
echo -e "${YELLOW}复制后端文件...${NC}"
cp "$PROJECT_ROOT/backend/services/data_service/main.py" "$TARGET_DIR/backend/main.py"
cp "$PROJECT_ROOT/backend/db.py" "$TARGET_DIR/backend/"
cp "$PROJECT_ROOT/backend/data.py" "$TARGET_DIR/backend/"
cp "$PROJECT_ROOT/backend/download_klines.py" "$TARGET_DIR/backend/"
cp "$PROJECT_ROOT/backend/binance_api.py" "$TARGET_DIR/backend/"
cp "$PROJECT_ROOT/backend/migrate.py" "$TARGET_DIR/backend/"
cp "$PROJECT_ROOT/backend/requirements.txt" "$TARGET_DIR/backend/"

# 复制前端文件
echo -e "${YELLOW}复制前端文件...${NC}"
if [ -d "$PROJECT_ROOT/frontend-data" ]; then
    cp -r "$PROJECT_ROOT/frontend-data"/* "$TARGET_DIR/frontend/"
else
    echo -e "${RED}警告: frontend-data 目录不存在，跳过前端文件复制${NC}"
fi

# 创建配置文件
echo -e "${YELLOW}创建配置文件...${NC}"

# backend/config.py
cat > "$TARGET_DIR/backend/config.py" << 'EOF'
"""
数据管理服务配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
backend_dir = Path(__file__).parent
project_root = backend_dir.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# 数据库配置
DB_PATH = os.getenv("DB_PATH", str(project_root / "data" / "crypto_data.db"))

# 服务配置
SERVICE_PORT = int(os.getenv("DATA_SERVICE_PORT", "8001"))
SERVICE_HOST = os.getenv("DATA_SERVICE_HOST", "0.0.0.0")

# CORS配置
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    # 添加生产环境域名
]

# 币安API配置
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_BASE_PATH = os.getenv("BINANCE_BASE_PATH", "")

# PostgreSQL配置（用于迁移）
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "crypto_data")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
EOF

# backend/__init__.py
touch "$TARGET_DIR/backend/__init__.py"

# .env.example
cat > "$TARGET_DIR/.env.example" << 'EOF'
# 数据库配置
DB_PATH=data/crypto_data.db

# 服务配置
DATA_SERVICE_PORT=8001
DATA_SERVICE_HOST=0.0.0.0

# 币安API配置
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_BASE_PATH=https://fapi.binance.com

# PostgreSQL配置（用于迁移）
PG_HOST=localhost
PG_PORT=5432
PG_DB=crypto_data
PG_USER=postgres
PG_PASSWORD=your_password

# 前端配置
NEXT_PUBLIC_API_URL=http://localhost:8001
EOF

# .gitignore
cat > "$TARGET_DIR/.gitignore" << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# 数据文件
data/*.db
data/*.db-shm
data/*.db-wal
*.db
*.db-shm
*.db-wal

# 环境变量
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# Node
node_modules/
.next/
out/
dist/

# 日志
*.log
EOF

# README.md
cat > "$TARGET_DIR/README.md" << 'EOF'
# 加密货币数据管理系统

## 功能特性

- K线数据下载和管理
- 数据查询和检索
- 数据完整性检查
- 数据修复和重检
- 数据库迁移（SQLite → PostgreSQL）

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## API文档

启动后端服务后，访问 http://localhost:8001/docs 查看API文档。

## 环境配置

复制 `.env.example` 为 `.env` 并配置相关参数。
EOF

# Docker配置
cat > "$TARGET_DIR/backend/Dockerfile" << 'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
EOF

cat > "$TARGET_DIR/docker-compose.yml" << 'EOF'
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8001:8001"
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    environment:
      - DB_PATH=/app/data/crypto_data.db

  frontend:
    build: ./frontend
    ports:
      - "3001:3001"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8001
    depends_on:
      - backend
EOF

# 修改导入路径（使用sed）
echo -e "${YELLOW}修改导入路径...${NC}"

# 修改 backend/main.py
if [ -f "$TARGET_DIR/backend/main.py" ]; then
    sed -i.bak 's/from services\.shared\.config import/from config import/g' "$TARGET_DIR/backend/main.py"
    sed -i.bak 's/DATA_SERVICE_PORT/SERVICE_PORT/g' "$TARGET_DIR/backend/main.py"
    rm -f "$TARGET_DIR/backend/main.py.bak"
fi

# 修改 backend/db.py
if [ -f "$TARGET_DIR/backend/db.py" ]; then
    # 在文件开头添加导入
    sed -i.bak '1i\
from config import DB_PATH as db_path\
' "$TARGET_DIR/backend/db.py"
    # 注释掉原有的路径设置代码（需要手动检查）
    rm -f "$TARGET_DIR/backend/db.py.bak"
fi

echo -e "${GREEN}项目创建完成！${NC}"
echo ""
echo -e "下一步："
echo -e "1. cd $TARGET_DIR"
echo -e "2. cp .env.example .env"
echo -e "3. 编辑 .env 文件配置参数"
echo -e "4. cd backend && pip install -r requirements.txt"
echo -e "5. python main.py"
echo ""
echo -e "${YELLOW}注意: 请检查并手动修改以下文件的导入路径：${NC}"
echo -e "- backend/db.py (数据库路径配置)"
echo -e "- backend/binance_api.py (环境变量加载)"
echo -e "- backend/data.py (如果有依赖)"
echo -e "- backend/download_klines.py (如果有依赖)"
