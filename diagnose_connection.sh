#!/bin/bash

# 终端连接诊断脚本

SERVER_IP="${1:-8.216.33.6}"
SSH_USER="${2:-root}"

echo "=== 终端连接诊断 ==="
echo "服务器: $SSH_USER@$SERVER_IP"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. 测试网络连通性
echo -e "${BLUE}1. 测试网络连通性...${NC}"
if ping -c 3 -W 2 $SERVER_IP &> /dev/null; then
    echo -e "${GREEN}✓ 服务器可达${NC}"
    PING_SUCCESS=true
else
    echo -e "${RED}✗ 服务器不可达${NC}"
    echo "   可能原因：服务器离线、IP错误、网络问题"
    PING_SUCCESS=false
fi
echo ""

# 2. 测试 SSH 端口
echo -e "${BLUE}2. 测试 SSH 端口 (22)...${NC}"
if command -v nc &> /dev/null; then
    if nc -zv -w 5 $SERVER_IP 22 &> /dev/null; then
        echo -e "${GREEN}✓ SSH端口开放${NC}"
        SSH_PORT_OPEN=true
    else
        echo -e "${RED}✗ SSH端口关闭或无法访问${NC}"
        echo "   可能原因：SSH服务未运行、防火墙阻止、端口被修改"
        SSH_PORT_OPEN=false
    fi
elif command -v timeout &> /dev/null; then
    if timeout 5 bash -c "echo >/dev/tcp/$SERVER_IP/22" 2>/dev/null; then
        echo -e "${GREEN}✓ SSH端口开放${NC}"
        SSH_PORT_OPEN=true
    else
        echo -e "${RED}✗ SSH端口关闭或无法访问${NC}"
        SSH_PORT_OPEN=false
    fi
else
    echo -e "${YELLOW}⚠ 无法测试端口（需要 nc 或 timeout 命令）${NC}"
    SSH_PORT_OPEN=unknown
fi
echo ""

# 3. 测试 SSH 连接
echo -e "${BLUE}3. 测试 SSH 连接...${NC}"
if ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no $SSH_USER@$SERVER_IP echo "连接成功" 2>/dev/null; then
    echo -e "${GREEN}✓ SSH连接成功${NC}"
    SSH_CONNECT=true
else
    echo -e "${RED}✗ SSH连接失败${NC}"
    echo "   尝试获取详细错误信息..."
    ssh -v -o ConnectTimeout=5 $SSH_USER@$SERVER_IP echo "test" 2>&1 | grep -E "(Connecting|Authenticating|Connection|Permission|refused|closed|timeout)" | head -5 || true
    SSH_CONNECT=false
fi
echo ""

# 4. 检查 Docker（如果能连接）
if [ "$SSH_CONNECT" = true ]; then
    echo -e "${BLUE}4. 检查 Docker 容器状态...${NC}"
    DOCKER_OUTPUT=$(ssh -o ConnectTimeout=5 $SSH_USER@$SERVER_IP "docker ps 2>&1")
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Docker 服务正常${NC}"
        echo ""
        echo "运行中的容器："
        ssh -o ConnectTimeout=5 $SSH_USER@$SERVER_IP "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'" 2>/dev/null || echo "无法获取容器列表"
    else
        echo -e "${YELLOW}⚠ Docker 服务异常或未安装${NC}"
        echo "$DOCKER_OUTPUT" | head -3
    fi
    echo ""
    
    # 5. 检查磁盘空间
    echo -e "${BLUE}5. 检查磁盘空间...${NC}"
    DISK_INFO=$(ssh -o ConnectTimeout=5 $SSH_USER@$SERVER_IP "df -h / 2>&1" | tail -1)
    if [ $? -eq 0 ]; then
        echo "$DISK_INFO"
        USAGE=$(echo "$DISK_INFO" | awk '{print $5}' | sed 's/%//')
        if [ ! -z "$USAGE" ] && [ "$USAGE" -gt 90 ]; then
            echo -e "${RED}⚠ 警告：磁盘使用率超过 90%！${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ 无法检查磁盘空间${NC}"
    fi
    echo ""
    
    # 6. 检查服务状态
    echo -e "${BLUE}6. 检查关键服务状态...${NC}"
    ssh -o ConnectTimeout=5 $SSH_USER@$SERVER_IP "
        echo 'SSH 服务:'
        systemctl is-active sshd 2>/dev/null || service ssh status 2>/dev/null | head -1 || echo '未知'
        echo ''
        echo 'Docker 服务:'
        systemctl is-active docker 2>/dev/null || service docker status 2>/dev/null | head -1 || echo '未安装或未运行'
    " 2>/dev/null || echo -e "${YELLOW}⚠ 无法检查服务状态${NC}"
    echo ""
else
    echo -e "${YELLOW}4-6. 跳过 Docker 和服务检查（需要先解决 SSH 连接问题）${NC}"
    echo ""
fi

# 总结
echo "=== 诊断总结 ==="
if [ "$PING_SUCCESS" = true ] && [ "$SSH_PORT_OPEN" = true ] && [ "$SSH_CONNECT" = true ]; then
    echo -e "${GREEN}✓ 所有检查通过，连接正常${NC}"
elif [ "$PING_SUCCESS" = false ]; then
    echo -e "${RED}✗ 服务器不可达，请检查：${NC}"
    echo "   - IP 地址是否正确"
    echo "   - 服务器是否在线"
    echo "   - 网络连接是否正常"
elif [ "$SSH_PORT_OPEN" = false ]; then
    echo -e "${RED}✗ SSH 端口无法访问，请检查：${NC}"
    echo "   - SSH 服务是否运行（通过云控制台 VNC 访问）"
    echo "   - 防火墙是否允许 SSH 端口"
    echo "   - 安全组规则是否正确"
elif [ "$SSH_CONNECT" = false ]; then
    echo -e "${RED}✗ SSH 连接失败，请检查：${NC}"
    echo "   - SSH 密钥是否正确"
    echo "   - 用户名和密码是否正确"
    echo "   - SSH 配置是否允许该用户登录"
else
    echo -e "${YELLOW}⚠ 部分检查失败，请查看上面的详细信息${NC}"
fi
echo ""

echo "提示：如果无法 SSH 连接，可以尝试："
echo "  1. 通过云服务器控制台的 VNC/Web 终端访问"
echo "  2. 检查安全组规则是否允许 SSH 端口"
echo "  3. 重启 SSH 服务：sudo systemctl restart sshd"
