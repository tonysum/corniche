#!/bin/bash

# PostgreSQL 用户检查和修复脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
echo "  PostgreSQL 用户检查和修复"
echo "=========================================="
echo ""

# 检查 _postgres 用户是否存在
log_info "1. 检查 _postgres 用户..."
if id "_postgres" &>/dev/null; then
    log_success "_postgres 用户存在"
    id _postgres
else
    log_warning "_postgres 用户不存在"
    echo ""
    log_info "创建 _postgres 用户..."
    
    # 创建 _postgres 用户
    sudo dscl . -create /Users/_postgres
    sudo dscl . -create /Users/_postgres UserShell /usr/bin/false
    sudo dscl . -create /Users/_postgres UniqueID 401
    sudo dscl . -create /Users/_postgres PrimaryGroupID 401
    sudo dscl . -create /Users/_postgres NFSHomeDirectory /var/empty
    sudo dscl . -create /Users/_postgres RealName "PostgreSQL Server"
    
    # 验证用户创建
    if id "_postgres" &>/dev/null; then
        log_success "_postgres 用户已创建"
        id _postgres
    else
        log_error "用户创建失败"
        exit 1
    fi
fi
echo ""

# 检查替代方法
log_info "2. 测试用户切换方法..."
echo ""

log_info "方法1: sudo -u _postgres"
if sudo -u _postgres whoami 2>/dev/null; then
    log_success "sudo -u _postgres 可用"
    USE_METHOD="sudo -u _postgres"
else
    log_warning "sudo -u _postgres 不可用"
    USE_METHOD=""
fi
echo ""

log_info "方法2: sudo su _postgres"
if sudo su _postgres -c "whoami" 2>/dev/null; then
    log_success "sudo su _postgres 可用"
    if [ -z "$USE_METHOD" ]; then
        USE_METHOD="sudo su _postgres -c"
    fi
else
    log_warning "sudo su _postgres 不可用"
fi
echo ""

# 显示初始化命令
log_info "3. 数据库初始化命令："
echo ""

if [ -n "$USE_METHOD" ]; then
    if [ "$USE_METHOD" = "sudo -u _postgres" ]; then
        log_info "使用命令："
        echo "  sudo -u _postgres /opt/local/lib/postgresql15/bin/initdb -D /opt/local/var/db/postgresql15/defaultdb"
        echo ""
        log_info "或者使用当前用户（如果允许）："
        echo "  /opt/local/lib/postgresql15/bin/initdb -D /opt/local/var/db/postgresql15/defaultdb -U \$(whoami)"
    else
        log_info "使用命令："
        echo "  sudo su _postgres -c '/opt/local/lib/postgresql15/bin/initdb -D /opt/local/var/db/postgresql15/defaultdb'"
    fi
else
    log_warning "无法切换到 _postgres 用户"
    log_info "尝试使用当前用户初始化（不推荐，但可以工作）："
    echo "  /opt/local/lib/postgresql15/bin/initdb -D /opt/local/var/db/postgresql15/defaultdb"
    echo ""
    log_info "或者手动创建用户后重试"
fi
echo ""

# 检查数据目录
log_info "4. 检查数据目录..."
DATA_DIR="/opt/local/var/db/postgresql15/defaultdb"
PARENT_DIR=$(dirname "$DATA_DIR")

if [ ! -d "$PARENT_DIR" ]; then
    log_info "创建父目录: $PARENT_DIR"
    sudo mkdir -p "$PARENT_DIR"
    sudo chown root:wheel "$PARENT_DIR"
    sudo chmod 755 "$PARENT_DIR"
fi

if [ -d "$DATA_DIR" ]; then
    if sudo test -f "$DATA_DIR/postgresql.conf" 2>/dev/null; then
        log_success "数据库已初始化"
    else
        log_warning "目录存在但未初始化"
    fi
else
    log_info "数据目录不存在，需要初始化"
fi
echo ""

# 提供完整初始化步骤
log_info "5. 完整初始化步骤："
echo ""
echo "步骤1: 确保 _postgres 用户存在（已完成）"
echo "步骤2: 创建数据目录（如果需要）"
echo "  sudo mkdir -p $DATA_DIR"
echo ""
echo "步骤3: 初始化数据库"
if [ "$USE_METHOD" = "sudo -u _postgres" ]; then
    echo "  sudo -u _postgres /opt/local/lib/postgresql15/bin/initdb -D $DATA_DIR"
else
    echo "  sudo su _postgres -c '/opt/local/lib/postgresql15/bin/initdb -D $DATA_DIR'"
fi
echo ""
echo "步骤4: 设置权限"
echo "  sudo chown -R _postgres:_postgres $DATA_DIR"
echo "  sudo chmod 700 $DATA_DIR"
echo ""
