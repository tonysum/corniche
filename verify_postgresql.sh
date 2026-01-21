#!/bin/bash

# PostgreSQL 服务验证脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PG_VERSION="${PG_VERSION:-15}"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "=========================================="
echo "  PostgreSQL 服务验证"
echo "=========================================="
echo ""

# 1. 检查进程
log_info "1. 检查 PostgreSQL 进程..."
if ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
    log_success "PostgreSQL 进程正在运行"
    ps aux | grep '[p]ostgres' | grep -v grep | head -3
else
    log_error "PostgreSQL 进程未运行"
fi
echo ""

# 2. 检查端口
log_info "2. 检查端口 5432..."
if lsof -i :5432 > /dev/null 2>&1; then
    log_success "端口 5432 正在监听"
    lsof -i :5432 | head -3
else
    log_warning "端口 5432 未在监听"
fi
echo ""

# 3. 检查套接字文件
log_info "3. 检查套接字文件..."
if [ -S "/tmp/.s.PGSQL.5432" ] || [ -e "/tmp/.s.PGSQL.5432" ]; then
    log_success "找到套接字文件: /tmp/.s.PGSQL.5432"
    ls -la /tmp/.s.PGSQL.5432 2>/dev/null || true
else
    log_warning "未找到套接字文件 /tmp/.s.PGSQL.5432"
fi
echo ""

# 4. 检查服务状态
log_info "4. 检查 MacPorts 服务状态..."
if command -v port &> /dev/null; then
    if sudo port installed postgresql${PG_VERSION}-server 2>/dev/null | grep -q "active"; then
        log_success "postgresql${PG_VERSION}-server 已安装并激活"
    else
        log_warning "postgresql${PG_VERSION}-server 状态未知"
    fi
else
    log_warning "MacPorts 未安装"
fi
echo ""

# 5. 测试连接
log_info "5. 测试数据库连接..."
if sudo su _postgres -c "psql -d postgres -c 'SELECT version();'" 2>/dev/null | head -3; then
    log_success "数据库连接成功！"
else
    log_warning "数据库连接失败"
    log_info "尝试使用 TCP/IP 连接..."
    if sudo su _postgres -c "psql -h localhost -d postgres -c 'SELECT version();'" 2>/dev/null | head -3; then
        log_success "TCP/IP 连接成功！"
    else
        log_error "所有连接方式都失败"
    fi
fi
echo ""

# 6. 显示连接信息
log_info "6. 连接信息："
echo "  主机: localhost"
echo "  端口: 5432"
echo "  默认用户: _postgres"
echo "  默认数据库: postgres"
echo ""
log_info "连接命令："
echo "  psql -d postgres"
echo "  或: sudo su _postgres -c 'psql -d postgres'"
echo "  或: psql -h localhost -U _postgres -d postgres"
echo ""
