#!/bin/bash

# Docker 服务更新脚本
# 使用方法: ./update-docker.sh [backend|frontend|all]

set -e  # 遇到错误立即退出

SERVICE=${1:-all}  # 默认更新所有服务
USE_CN=${2:-false}  # 是否使用国内镜像源

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 选择 docker-compose 文件
if [ "$USE_CN" = "true" ] || [ "$USE_CN" = "cn" ]; then
    COMPOSE_FILE="docker-compose.cn.yml"
    echo -e "${YELLOW}使用国内镜像源配置${NC}"
else
    COMPOSE_FILE="docker-compose.yml"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}开始更新 Docker 服务: $SERVICE${NC}"
echo -e "${GREEN}========================================${NC}"

# 备份数据
echo -e "\n${YELLOW}[1/5] 备份数据...${NC}"
if [ -f "db/crypto_data.db" ]; then
    BACKUP_FILE="db/crypto_data.db.backup.$(date +%Y%m%d_%H%M%S)"
    cp db/crypto_data.db "$BACKUP_FILE" 2>/dev/null && \
        echo -e "${GREEN}✓ 数据库已备份: $BACKUP_FILE${NC}" || \
        echo -e "${YELLOW}⚠ 数据库备份失败（可能文件不存在）${NC}"
else
    echo -e "${YELLOW}⚠ 数据库文件不存在，跳过备份${NC}"
fi

# 停止现有容器
echo -e "\n${YELLOW}[2/5] 停止现有容器...${NC}"
docker-compose -f "$COMPOSE_FILE" down || true

# 清理旧镜像（可选）
read -p "是否清理未使用的镜像？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}清理未使用的镜像...${NC}"
    docker image prune -f
fi

# 重新构建并启动
echo -e "\n${YELLOW}[3/5] 重新构建并启动服务...${NC}"
if [ "$SERVICE" = "all" ]; then
    docker-compose -f "$COMPOSE_FILE" up -d --build
elif [ "$SERVICE" = "backend" ]; then
    docker-compose -f "$COMPOSE_FILE" up -d --build backend
elif [ "$SERVICE" = "frontend" ]; then
    docker-compose -f "$COMPOSE_FILE" up -d --build frontend
else
    echo -e "${RED}错误: 未知的服务名称 '$SERVICE'${NC}"
    echo "使用方法: ./update-docker.sh [backend|frontend|all] [cn]"
    exit 1
fi

# 等待服务启动
echo -e "\n${YELLOW}[4/5] 等待服务启动...${NC}"
sleep 5

# 检查服务状态
echo -e "\n${YELLOW}[5/5] 检查服务状态...${NC}"
docker-compose -f "$COMPOSE_FILE" ps

# 健康检查
echo -e "\n${YELLOW}健康检查...${NC}"
if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "backend" ]; then
    echo -n "检查后端服务... "
    if curl -f -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 后端服务正常${NC}"
    else
        echo -e "${RED}✗ 后端服务异常${NC}"
        echo "查看日志: docker-compose -f $COMPOSE_FILE logs backend"
    fi
fi

if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "frontend" ]; then
    echo -n "检查前端服务... "
    if curl -f -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 前端服务正常${NC}"
    else
        echo -e "${YELLOW}⚠ 前端服务可能还在启动中...${NC}"
    fi
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}更新完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "查看日志: docker-compose -f $COMPOSE_FILE logs -f"
echo "停止服务: docker-compose -f $COMPOSE_FILE down"
echo "访问前端: http://localhost:3000"
echo "访问后端: http://localhost:8000"

