#!/usr/bin/env python3
"""
数据管理模块独立项目创建脚本
用法: python scripts/create_data_manager_project.py [目标目录]
"""

import os
import shutil
import sys
from pathlib import Path

def create_project(target_dir: str = None):
    """创建独立的数据管理项目"""
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # 目标目录
    if target_dir is None:
        target_dir = project_root.parent / "crypto-data-manager"
    else:
        target_dir = Path(target_dir)
    
    print(f"源项目: {project_root}")
    print(f"目标目录: {target_dir}")
    print()
    
    # 创建目录结构
    print("创建目录结构...")
    dirs = [
        target_dir / "backend",
        target_dir / "frontend" / "app",
        target_dir / "frontend" / "components",
        target_dir / "frontend" / "contexts",
        target_dir / "frontend" / "lib",
        target_dir / "data",
        target_dir / "scripts",
        target_dir / "docs",
    ]
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # 复制后端文件
    print("复制后端文件...")
    backend_files = {
        "services/data_service/main.py": "backend/main.py",
        "db.py": "backend/db.py",
        "data.py": "backend/data.py",
        "download_klines.py": "backend/download_klines.py",
        "binance_api.py": "backend/binance_api.py",
        "migrate.py": "backend/migrate.py",
        "requirements.txt": "backend/requirements.txt",
    }
    
    for src, dst in backend_files.items():
        src_path = project_root / "backend" / src
        dst_path = target_dir / dst
        if src_path.exists():
            shutil.copy2(src_path, dst_path)
            print(f"  ✓ {src} -> {dst}")
        else:
            print(f"  ✗ {src} 不存在，跳过")
    
    # 复制前端文件
    print("\n复制前端文件...")
    frontend_src = project_root / "frontend-data"
    frontend_dst = target_dir / "frontend"
    if frontend_src.exists():
        # 复制所有文件
        for item in frontend_src.iterdir():
            if item.name not in ['.git', 'node_modules', '.next']:
                if item.is_dir():
                    shutil.copytree(item, frontend_dst / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, frontend_dst / item.name)
        print(f"  ✓ frontend-data -> frontend")
    else:
        print(f"  ✗ frontend-data 目录不存在，跳过前端文件复制")
    
    # 创建配置文件
    print("\n创建配置文件...")
    
    # backend/config.py
    config_content = '''"""
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
'''
    (target_dir / "backend" / "config.py").write_text(config_content, encoding='utf-8')
    print("  ✓ backend/config.py")
    
    # backend/__init__.py
    (target_dir / "backend" / "__init__.py").write_text("", encoding='utf-8')
    print("  ✓ backend/__init__.py")
    
    # .env.example
    env_example = '''# 数据库配置
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
'''
    (target_dir / ".env.example").write_text(env_example, encoding='utf-8')
    print("  ✓ .env.example")
    
    # .gitignore
    gitignore = '''# Python
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
'''
    (target_dir / ".gitignore").write_text(gitignore, encoding='utf-8')
    print("  ✓ .gitignore")
    
    # README.md
    readme = '''# 加密货币数据管理系统

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
source venv/bin/activate  # Windows: venv\\Scripts\\activate
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
'''
    (target_dir / "README.md").write_text(readme, encoding='utf-8')
    print("  ✓ README.md")
    
    # Docker配置
    dockerfile = '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
'''
    (target_dir / "backend" / "Dockerfile").write_text(dockerfile, encoding='utf-8')
    print("  ✓ backend/Dockerfile")
    
    docker_compose = '''version: '3.8'

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
'''
    (target_dir / "docker-compose.yml").write_text(docker_compose, encoding='utf-8')
    print("  ✓ docker-compose.yml")
    
    # 修改导入路径
    print("\n修改导入路径...")
    
    # 修改 backend/main.py
    main_py = target_dir / "backend" / "main.py"
    if main_py.exists():
        content = main_py.read_text(encoding='utf-8')
        content = content.replace(
            'from services.shared.config import DATA_SERVICE_PORT, ALLOWED_ORIGINS',
            'from config import SERVICE_PORT as DATA_SERVICE_PORT, ALLOWED_ORIGINS'
        )
        main_py.write_text(content, encoding='utf-8')
        print("  ✓ backend/main.py")
    
    print("\n" + "="*60)
    print("项目创建完成！")
    print("="*60)
    print(f"\n下一步：")
    print(f"1. cd {target_dir}")
    print(f"2. cp .env.example .env")
    print(f"3. 编辑 .env 文件配置参数")
    print(f"4. cd backend && pip install -r requirements.txt")
    print(f"5. python main.py")
    print(f"\n注意: 请检查并手动修改以下文件的导入路径：")
    print(f"- backend/db.py (数据库路径配置)")
    print(f"- backend/binance_api.py (环境变量加载)")
    print(f"- backend/data.py (如果有依赖)")
    print(f"- backend/download_klines.py (如果有依赖)")

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else None
    create_project(target_dir)
