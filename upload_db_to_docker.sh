#!/bin/bash

# 数据库文件上传到Docker容器脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DB_FILE="data/crypto_data.db"

# 检查数据库文件
if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}错误: 数据库文件不存在: $DB_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}=== 上传数据库文件到Docker容器 ===${NC}\n"

# 读取宿主机IP
read -p "请输入Docker宿主机IP地址: " HOST_IP
if [ -z "$HOST_IP" ]; then
    echo -e "${RED}错误: 宿主机IP不能为空${NC}"
    exit 1
fi

# 读取容器名称（可选）
read -p "请输入容器名称（默认: corniche）: " CONTAINER_NAME
CONTAINER_NAME=${CONTAINER_NAME:-corniche}

# 读取用户名
read -p "请输入SSH用户名（默认: root）: " SSH_USER
SSH_USER=${SSH_USER:-root}

# 检查是否使用密钥文件
read -p "是否使用SSH密钥文件? (y/n): " USE_KEY
if [ "$USE_KEY" = "y" ]; then
    read -p "请输入密钥文件路径: " KEY_FILE
    if [ ! -f "$KEY_FILE" ]; then
        echo -e "${RED}错误: 密钥文件不存在: $KEY_FILE${NC}"
        exit 1
    fi
    SSH_OPTIONS="-i $KEY_FILE"
else
    SSH_OPTIONS=""
fi

echo ""
echo -e "${GREEN}配置信息:${NC}"
echo "  数据库文件: $DB_FILE"
echo "  文件大小: $(du -h "$DB_FILE" | cut -f1)"
echo "  宿主机IP: $HOST_IP"
echo "  容器名称: $CONTAINER_NAME"
echo "  SSH用户: $SSH_USER"
echo ""

read -p "确认上传? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "已取消"
    exit 0
fi

echo ""
echo -e "${GREEN}1. 上传文件到宿主机临时目录...${NC}"
scp $SSH_OPTIONS "$DB_FILE" $SSH_USER@$HOST_IP:/tmp/crypto_data.db

echo ""
echo -e "${GREEN}2. 查找容器...${NC}"
CONTAINER_ID=$(ssh $SSH_OPTIONS $SSH_USER@$HOST_IP "docker ps -q -f name=$CONTAINER_NAME" | head -1)

if [ -z "$CONTAINER_ID" ]; then
    echo -e "${YELLOW}警告: 未找到容器 '$CONTAINER_NAME'，尝试查找所有容器...${NC}"
    ssh $SSH_OPTIONS $SSH_USER@$HOST_IP "docker ps"
    read -p "请输入容器ID或名称: " CONTAINER_ID
fi

echo ""
echo -e "${GREEN}3. 复制文件到容器...${NC}"
ssh $SSH_OPTIONS $SSH_USER@$HOST_IP "docker cp /tmp/crypto_data.db $CONTAINER_ID:/opt/corniche/data/"

echo ""
echo -e "${GREEN}4. 设置文件权限...${NC}"
ssh $SSH_OPTIONS $SSH_USER@$HOST_IP "docker exec $CONTAINER_ID chmod 644 /opt/corniche/data/crypto_data.db"

echo ""
echo -e "${GREEN}5. 清理临时文件...${NC}"
ssh $SSH_OPTIONS $SSH_USER@$HOST_IP "rm /tmp/crypto_data.db"

echo ""
echo -e "${GREEN}6. 验证文件...${NC}"
REMOTE_SIZE=$(ssh $SSH_OPTIONS $SSH_USER@$HOST_IP "docker exec $CONTAINER_ID ls -lh /opt/corniche/data/crypto_data.db 2>/dev/null | awk '{print \$5}'" || echo "未知")
LOCAL_SIZE=$(du -h "$DB_FILE" | cut -f1)

echo "  本地文件大小: $LOCAL_SIZE"
echo "  容器内文件大小: $REMOTE_SIZE"

echo ""
echo -e "${GREEN}✓ 上传完成！${NC}"
echo ""
echo "提示: 如果服务需要重启才能识别新数据库，请执行:"
echo "  ssh $SSH_USER@$HOST_IP 'cd /opt/corniche && docker-compose restart'"
