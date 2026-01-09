#!/bin/bash

# Nginx 配置部署脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Nginx 配置部署工具 ===${NC}\n"

# 检查是否是 root 用户
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误: 请使用 sudo 运行此脚本${NC}"
    exit 1
fi

# 读取域名
read -p "请输入您的域名 (例如: example.com): " DOMAIN
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}错误: 域名不能为空${NC}"
    exit 1
fi

# 检查 Nginx 是否已安装
if ! command -v nginx &> /dev/null; then
    echo -e "${YELLOW}Nginx 未安装，正在安装...${NC}"
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y nginx
    elif command -v yum &> /dev/null; then
        yum install -y nginx
    else
        echo -e "${RED}错误: 无法自动安装 Nginx，请手动安装${NC}"
        exit 1
    fi
fi

# 创建配置文件
CONFIG_FILE="/etc/nginx/sites-available/corniche"
echo -e "${GREEN}创建配置文件: $CONFIG_FILE${NC}"

# 读取模板并替换域名
sed "s/yourdomain.com/$DOMAIN/g" nginx-corniche.conf > "$CONFIG_FILE"

# 创建符号链接
echo -e "${GREEN}启用配置...${NC}"
ln -sf "$CONFIG_FILE" /etc/nginx/sites-enabled/corniche

# 测试配置
echo -e "${GREEN}测试 Nginx 配置...${NC}"
if nginx -t; then
    echo -e "${GREEN}✓ 配置测试通过${NC}"
else
    echo -e "${RED}✗ 配置测试失败${NC}"
    exit 1
fi

# 询问是否配置 SSL
read -p "是否配置 SSL 证书 (Let's Encrypt)? (y/n): " SETUP_SSL
if [ "$SETUP_SSL" = "y" ]; then
    # 检查 certbot 是否已安装
    if ! command -v certbot &> /dev/null; then
        echo -e "${YELLOW}安装 Certbot...${NC}"
        if command -v apt-get &> /dev/null; then
            apt-get install -y certbot python3-certbot-nginx
        elif command -v yum &> /dev/null; then
            yum install -y certbot python3-certbot-nginx
        fi
    fi
    
    echo -e "${GREEN}获取 SSL 证书...${NC}"
    certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" || {
        echo -e "${YELLOW}警告: SSL 证书获取失败，请稍后手动运行:${NC}"
        echo "  certbot --nginx -d $DOMAIN -d www.$DOMAIN"
    }
fi

# 重新加载 Nginx
echo -e "${GREEN}重新加载 Nginx...${NC}"
systemctl reload nginx

echo ""
echo -e "${GREEN}=== 部署完成 ===${NC}"
echo ""
echo "配置信息:"
echo "  域名: $DOMAIN"
echo "  配置文件: $CONFIG_FILE"
echo "  访问地址: http://$DOMAIN (HTTP 会自动重定向到 HTTPS)"
echo ""
echo "下一步:"
echo "  1. 确保后端服务运行在:"
echo "     - 数据服务: localhost:8001"
echo "     - 回测服务: localhost:8002"
echo "     - 订单服务: localhost:8003"
echo "     - 前端: localhost:3000"
echo ""
echo "  2. 更新前端环境变量:"
echo "     NEXT_PUBLIC_DATA_SERVICE_URL=https://$DOMAIN/api/data"
echo "     NEXT_PUBLIC_BACKTEST_SERVICE_URL=https://$DOMAIN/api/backtest"
echo "     NEXT_PUBLIC_ORDER_SERVICE_URL=https://$DOMAIN/api/order"
echo ""
echo "  3. 测试访问:"
echo "     curl https://$DOMAIN"
echo "     curl https://$DOMAIN/api/data/"
