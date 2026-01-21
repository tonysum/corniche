#!/bin/bash

# PostgreSQL 数据目录检查脚本
# 使用正确的权限检查数据目录

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
echo "  PostgreSQL 数据目录检查"
echo "=========================================="
echo ""

# 数据目录路径
DATA_DIR="/opt/local/var/db/postgresql${PG_VERSION}/defaultdb"

log_info "检查数据目录: $DATA_DIR"
echo ""

# 1. 检查目录是否存在
log_info "1. 检查目录是否存在..."
if [ -d "$DATA_DIR" ]; then
    log_success "目录存在"
else
    log_error "目录不存在"
    log_info "可能需要初始化数据库"
    echo ""
    log_info "初始化命令："
    echo "  sudo su _postgres -c '/opt/local/lib/postgresql${PG_VERSION}/bin/initdb -D $DATA_DIR'"
    exit 1
fi
echo ""

# 2. 检查目录权限（使用 sudo）
log_info "2. 检查目录权限和所有者..."
if sudo ls -ld "$DATA_DIR" 2>/dev/null; then
    OWNER=$(sudo ls -ld "$DATA_DIR" | awk '{print $3}')
    GROUP=$(sudo ls -ld "$DATA_DIR" | awk '{print $4}')
    PERMS=$(sudo ls -ld "$DATA_DIR" | awk '{print $1}')
    
    log_info "所有者: $OWNER"
    log_info "组: $GROUP"
    log_info "权限: $PERMS"
    
    if [ "$OWNER" = "_postgres" ]; then
        log_success "所有者正确 (_postgres)"
    else
        log_warning "所有者不正确，应该是 _postgres"
        log_info "修复命令："
        echo "  sudo chown -R _postgres:_postgres $DATA_DIR"
    fi
    
    if [ "$PERMS" = "drwx------" ] || [ "$PERMS" = "drwx------+" ]; then
        log_success "权限正确 (700)"
    else
        log_warning "权限可能不正确，应该是 700"
        log_info "修复命令："
        echo "  sudo chmod 700 $DATA_DIR"
    fi
else
    log_error "无法访问目录"
fi
echo ""

# 3. 检查目录内容
log_info "3. 检查目录内容..."
if sudo ls -la "$DATA_DIR" 2>/dev/null | head -20; then
    FILE_COUNT=$(sudo ls -A "$DATA_DIR" 2>/dev/null | wc -l | tr -d ' ')
    log_info "文件数量: $FILE_COUNT"
    
    if [ "$FILE_COUNT" -eq 0 ]; then
        log_warning "目录为空，数据库可能未初始化"
    else
        log_success "目录包含文件"
        
        # 检查关键文件
        log_info "检查关键文件..."
        if sudo test -f "$DATA_DIR/postgresql.conf"; then
            log_success "✓ postgresql.conf 存在"
        else
            log_warning "✗ postgresql.conf 不存在"
        fi
        
        if sudo test -f "$DATA_DIR/pg_hba.conf"; then
            log_success "✓ pg_hba.conf 存在"
        else
            log_warning "✗ pg_hba.conf 不存在"
        fi
        
        if sudo test -f "$DATA_DIR/postmaster.pid"; then
            log_warning "✗ postmaster.pid 存在（服务可能正在运行）"
            sudo cat "$DATA_DIR/postmaster.pid" 2>/dev/null || true
        else
            log_info "✓ postmaster.pid 不存在（服务未运行）"
        fi
    fi
else
    log_error "无法列出目录内容"
fi
echo ""

# 4. 检查磁盘空间
log_info "4. 检查磁盘空间..."
if df -h "$DATA_DIR" 2>/dev/null | tail -1; then
    log_success "磁盘空间检查完成"
else
    log_warning "无法检查磁盘空间"
fi
echo ""

# 5. 检查父目录
log_info "5. 检查父目录权限..."
PARENT_DIR=$(dirname "$DATA_DIR")
if sudo ls -ld "$PARENT_DIR" 2>/dev/null; then
    log_success "父目录可访问"
else
    log_warning "父目录访问受限"
fi
echo ""

# 6. 提供修复建议
log_info "6. 修复建议："
echo ""
echo "如果目录不存在或为空，初始化数据库："
echo "  sudo su _postgres -c '/opt/local/lib/postgresql${PG_VERSION}/bin/initdb -D $DATA_DIR'"
echo ""
echo "如果权限不正确，修复权限："
echo "  sudo chown -R _postgres:_postgres $DATA_DIR"
echo "  sudo chmod 700 $DATA_DIR"
echo ""
echo "如果父目录不存在，创建目录："
echo "  sudo mkdir -p $PARENT_DIR"
echo "  sudo chown root:wheel $PARENT_DIR"
echo "  sudo chmod 755 $PARENT_DIR"
echo ""
