#!/bin/bash

# 服务器IP地址检查脚本

echo "=== 服务器IP地址信息 ==="
echo ""

echo "1. 内网IP地址:"
hostname -I 2>/dev/null || ip addr show | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | cut -d/ -f1
echo ""

echo "2. 详细网络接口信息:"
ip addr show 2>/dev/null | grep "inet " | grep -v 127.0.0.1 || ifconfig 2>/dev/null | grep "inet " | grep -v 127.0.0.1
echo ""

echo "3. 公网IP地址:"
PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || curl -s --max-time 5 ipinfo.io/ip 2>/dev/null || curl -s --max-time 5 icanhazip.com 2>/dev/null)
if [ -n "$PUBLIC_IP" ]; then
    echo "$PUBLIC_IP"
else
    echo "无法获取公网IP（可能没有公网IP或网络不通）"
fi
echo ""

echo "4. IP详细信息（如果可访问）:"
curl -s --max-time 5 ipinfo.io 2>/dev/null || echo "无法获取详细信息"
echo ""

echo "5. 默认网关:"
ip route show default 2>/dev/null | awk '{print $3}' || route -n 2>/dev/null | grep "^0.0.0.0" | awk '{print $2}'
echo ""

echo "=== 完成 ==="
