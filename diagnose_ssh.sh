#!/bin/bash

# SSH连接诊断脚本

SERVER="${1:-172.23.0.2}"
USER="${2:-root}"

echo "=== SSH连接诊断 ==="
echo "服务器: $USER@$SERVER"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. 测试网络连通性
echo "1. 测试网络连通性..."
if ping -c 3 -W 2 $SERVER &> /dev/null; then
    echo -e "${GREEN}✓ 服务器可达${NC}"
else
    echo -e "${RED}✗ 服务器不可达${NC}"
    echo "   提示: 检查IP地址是否正确，或服务器是否在线"
fi
echo ""

# 2. 测试SSH端口
echo "2. 测试SSH端口 (22)..."
if timeout 5 bash -c "echo >/dev/tcp/$SERVER/22" 2>/dev/null; then
    echo -e "${GREEN}✓ SSH端口开放${NC}"
else
    echo -e "${RED}✗ SSH端口关闭或无法访问${NC}"
    echo "   提示: 检查防火墙设置或SSH服务是否运行"
fi
echo ""

# 3. 测试SSH连接
echo "3. 测试SSH连接..."
if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no $USER@$SERVER echo "连接成功" 2>/dev/null; then
    echo -e "${GREEN}✓ SSH连接成功${NC}"
else
    echo -e "${RED}✗ SSH连接失败${NC}"
    echo "   提示: 查看下面的详细错误信息"
fi
echo ""

# 4. 显示SSH详细信息
echo "4. SSH连接详细信息:"
echo "---"
ssh -v -o ConnectTimeout=5 $USER@$SERVER echo "test" 2>&1 | grep -E "(Connecting|Authenticating|Connection|Permission|refused|closed)" | head -10
echo "---"
echo ""

# 5. 检查IP类型
echo "5. IP地址类型分析:"
if [[ $SERVER =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]; then
    echo -e "${YELLOW}⚠ 这是Docker内网IP (172.x.x.x)${NC}"
    echo "   提示: 无法从外部直接访问，需要使用宿主机IP"
elif [[ $SERVER =~ ^10\. ]] || [[ $SERVER =~ ^192\.168\. ]]; then
    echo -e "${YELLOW}⚠ 这是私有网络IP${NC}"
    echo "   提示: 需要公网IP或VPN才能从外部访问"
elif [[ $SERVER =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${GREEN}✓ 有效的IP地址格式${NC}"
else
    echo -e "${YELLOW}⚠ 无法确定IP类型${NC}"
fi
echo ""

# 6. 建议
echo "6. 建议的解决方法:"
echo "---"
if [[ $SERVER =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]; then
    echo "   1. 查找Docker宿主机IP: docker inspect container_name | grep IPAddress"
    echo "   2. 使用宿主机IP和映射端口连接"
    echo "   3. 或通过docker cp命令复制文件"
elif ! ping -c 1 -W 2 $SERVER &> /dev/null; then
    echo "   1. 检查服务器是否在线"
    echo "   2. 检查IP地址是否正确"
    echo "   3. 检查网络连接"
else
    echo "   1. 检查SSH服务: sudo systemctl status ssh"
    echo "   2. 检查防火墙: sudo ufw status"
    echo "   3. 检查SSH配置: sudo nano /etc/ssh/sshd_config"
    echo "   4. 尝试使用rsync: rsync -avz file user@server:/path/"
fi
echo "---"

echo ""
echo "=== 诊断完成 ==="
