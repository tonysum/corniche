#!/bin/bash

# 移除数据管理服务相关部分的脚本
# 注意：保留 db.py 和 data.py，因为它们被回测服务使用

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo -e "${GREEN}开始移除数据管理服务相关部分...${NC}"
echo -e "项目根目录: ${PROJECT_ROOT}"
echo ""

# 确认操作
read -p "确认要移除数据管理服务吗？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}操作已取消${NC}"
    exit 1
fi

# 1. 删除数据管理服务目录
echo -e "${YELLOW}删除数据管理服务目录...${NC}"
if [ -d "$PROJECT_ROOT/backend/services/data_service" ]; then
    rm -rf "$PROJECT_ROOT/backend/services/data_service"
    echo -e "${GREEN}  ✓ 已删除 backend/services/data_service${NC}"
else
    echo -e "${YELLOW}  ⚠  backend/services/data_service 不存在${NC}"
fi

# 2. 删除数据管理前端目录
echo -e "${YELLOW}删除数据管理前端目录...${NC}"
if [ -d "$PROJECT_ROOT/frontend-data" ]; then
    rm -rf "$PROJECT_ROOT/frontend-data"
    echo -e "${GREEN}  ✓ 已删除 frontend-data${NC}"
else
    echo -e "${YELLOW}  ⚠  frontend-data 不存在${NC}"
fi

# 3. 删除数据下载脚本（如果只被数据服务使用）
echo -e "${YELLOW}检查数据下载脚本...${NC}"
if [ -f "$PROJECT_ROOT/backend/download_klines.py" ]; then
    read -p "删除 download_klines.py？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$PROJECT_ROOT/backend/download_klines.py"
        echo -e "${GREEN}  ✓ 已删除 backend/download_klines.py${NC}"
    else
        echo -e "${YELLOW}  ⏭  保留 backend/download_klines.py${NC}"
    fi
fi

# 4. 删除数据库迁移脚本（如果只被数据服务使用）
echo -e "${YELLOW}检查数据库迁移脚本...${NC}"
if [ -f "$PROJECT_ROOT/backend/migrate.py" ]; then
    read -p "删除 migrate.py？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$PROJECT_ROOT/backend/migrate.py"
        echo -e "${GREEN}  ✓ 已删除 backend/migrate.py${NC}"
    else
        echo -e "${YELLOW}  ⏭  保留 backend/migrate.py${NC}"
    fi
fi

# 5. 更新共享配置
echo -e "${YELLOW}更新共享配置...${NC}"
CONFIG_FILE="$PROJECT_ROOT/backend/services/shared/config.py"
if [ -f "$CONFIG_FILE" ]; then
    # 移除 DATA_SERVICE_PORT
    sed -i.bak '/^DATA_SERVICE_PORT/d' "$CONFIG_FILE"
    # 移除数据管理前端的 CORS 配置
    sed -i.bak '/localhost:3001/d' "$CONFIG_FILE"
    sed -i.bak '/127.0.0.1:3001/d' "$CONFIG_FILE"
    sed -i.bak '/数据管理前端/d' "$CONFIG_FILE"
    rm -f "$CONFIG_FILE.bak"
    echo -e "${GREEN}  ✓ 已更新 backend/services/shared/config.py${NC}"
fi

# 6. 更新启动脚本
echo -e "${YELLOW}更新启动脚本...${NC}"
START_SCRIPT="$PROJECT_ROOT/backend/start-services.sh"
if [ -f "$START_SCRIPT" ]; then
    # 移除数据服务启动相关代码
    sed -i.bak '/data_service/d' "$START_SCRIPT"
    sed -i.bak '/DATA_SERVICE/d' "$START_SCRIPT"
    sed -i.bak '/数据管理服务/d' "$START_SCRIPT"
    rm -f "$START_SCRIPT.bak"
    echo -e "${GREEN}  ✓ 已更新 backend/start-services.sh${NC}"
fi

# 7. 更新 Docker Compose 配置
echo -e "${YELLOW}更新 Docker Compose 配置...${NC}"
DOCKER_COMPOSE="$PROJECT_ROOT/docker-compose.yml"
if [ -f "$DOCKER_COMPOSE" ]; then
    # 创建备份
    cp "$DOCKER_COMPOSE" "$DOCKER_COMPOSE.bak"
    
    # 使用 Python 脚本处理（更安全）
    python3 << 'PYTHON_SCRIPT'
import re

with open('docker-compose.yml.bak', 'r') as f:
    content = f.read()

# 移除 data-service 服务块
content = re.sub(r'  data-service:.*?networks:.*?- crypto-network\n', '', content, flags=re.DOTALL)

# 移除 frontend-data 服务块
content = re.sub(r'  frontend-data:.*?networks:.*?- crypto-network\n', '', content, flags=re.DOTALL)

# 移除 frontend-data 的依赖
content = re.sub(r'    depends_on:\s*\n\s+- data-service\n', '', content)

with open('docker-compose.yml', 'w') as f:
    f.write(content)

print("  ✓ 已更新 docker-compose.yml")
PYTHON_SCRIPT
    
    rm -f "$DOCKER_COMPOSE.bak"
fi

# 8. 更新 README
echo -e "${YELLOW}更新文档...${NC}"
README_FILE="$PROJECT_ROOT/backend/README.md"
if [ -f "$README_FILE" ]; then
    # 移除数据管理服务相关说明
    sed -i.bak '/### 1\. 数据管理服务/,/^### 2\./d' "$README_FILE"
    sed -i.bak '/数据管理服务/d' "$README_FILE"
    sed -i.bak '/8001/d' "$README_FILE"
    rm -f "$README_FILE.bak"
    echo -e "${GREEN}  ✓ 已更新 backend/README.md${NC}"
fi

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}数据管理服务相关部分已移除！${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "${YELLOW}注意：${NC}"
echo -e "1. 已保留 db.py 和 data.py（回测服务需要使用）"
echo -e "2. 已保留 binance_api.py（可能被其他模块使用）"
echo -e "3. 请手动检查以下文件："
echo -e "   - docker-compose.yml"
echo -e "   - backend/start-services.sh"
echo -e "   - 其他文档文件"
echo ""
