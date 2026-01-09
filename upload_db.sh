#!/bin/bash

# 数据库文件上传脚本
# 用于上传 crypto_data.db 到服务器

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== 数据库文件上传工具 ===${NC}\n"

# 配置
DB_FILE="data/crypto_data.db"
DB_SIZE=$(du -h "$DB_FILE" 2>/dev/null | cut -f1 || echo "未知")

# 检查数据库文件是否存在
if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}错误: 数据库文件不存在: $DB_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}数据库文件: $DB_FILE${NC}"
echo -e "${GREEN}文件大小: $DB_SIZE${NC}\n"

# 读取服务器信息
read -p "请输入服务器地址 (例如: user@192.168.1.100): " SERVER
if [ -z "$SERVER" ]; then
    echo -e "${RED}错误: 服务器地址不能为空${NC}"
    exit 1
fi

read -p "请输入服务器上的目标路径 (默认: /opt/corniche/data/): " REMOTE_PATH
REMOTE_PATH=${REMOTE_PATH:-/opt/corniche/data/}

read -p "是否使用密钥文件? (y/n): " USE_KEY
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

# 选择上传方式
echo -e "\n${YELLOW}选择上传方式:${NC}"
echo "1. SCP (简单快速)"
echo "2. rsync (支持断点续传，推荐大文件)"
echo "3. 压缩后上传 (适合网络较慢)"
read -p "请选择 (1-3): " METHOD

case $METHOD in
    1)
        echo -e "\n${GREEN}使用 SCP 上传...${NC}"
        # 创建远程目录
        ssh $SSH_OPTIONS $SERVER "mkdir -p $REMOTE_PATH"
        # 上传文件
        scp $SSH_OPTIONS "$DB_FILE" "$SERVER:$REMOTE_PATH"
        ;;
    2)
        echo -e "\n${GREEN}使用 rsync 上传（支持断点续传）...${NC}"
        # 创建远程目录
        ssh $SSH_OPTIONS $SERVER "mkdir -p $REMOTE_PATH"
        # 使用 rsync 上传
        if [ -n "$KEY_FILE" ]; then
            rsync -avz --progress -e "ssh $SSH_OPTIONS" "$DB_FILE" "$SERVER:$REMOTE_PATH"
        else
            rsync -avz --progress "$DB_FILE" "$SERVER:$REMOTE_PATH"
        fi
        ;;
    3)
        echo -e "\n${GREEN}压缩后上传...${NC}"
        # 压缩文件
        COMPRESSED_FILE="${DB_FILE}.tar.gz"
        echo "正在压缩文件..."
        tar czf "$COMPRESSED_FILE" -C data crypto_data.db
        
        # 上传压缩文件
        echo "正在上传压缩文件..."
        scp $SSH_OPTIONS "$COMPRESSED_FILE" "$SERVER:/tmp/"
        
        # 在服务器上解压
        echo "正在服务器上解压..."
        ssh $SSH_OPTIONS $SERVER "mkdir -p $REMOTE_PATH && cd $REMOTE_PATH && tar xzf /tmp/$(basename $COMPRESSED_FILE) && rm /tmp/$(basename $COMPRESSED_FILE)"
        
        # 删除本地压缩文件
        rm "$COMPRESSED_FILE"
        ;;
    *)
        echo -e "${RED}错误: 无效的选择${NC}"
        exit 1
        ;;
esac

# 设置权限
echo -e "\n${GREEN}设置文件权限...${NC}"
ssh $SSH_OPTIONS $SERVER "chmod 644 $REMOTE_PATH/crypto_data.db"

# 验证上传
echo -e "\n${GREEN}验证上传...${NC}"
REMOTE_SIZE=$(ssh $SSH_OPTIONS $SERVER "du -h $REMOTE_PATH/crypto_data.db 2>/dev/null | cut -f1" || echo "未知")
echo -e "${GREEN}本地文件大小: $DB_SIZE${NC}"
echo -e "${GREEN}远程文件大小: $REMOTE_SIZE${NC}"

if [ "$DB_SIZE" = "$REMOTE_SIZE" ]; then
    echo -e "\n${GREEN}✓ 上传成功！${NC}"
else
    echo -e "\n${YELLOW}⚠ 文件大小不一致，请检查${NC}"
fi

echo -e "\n${GREEN}=== 完成 ===${NC}"
