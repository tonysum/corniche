#!/bin/bash

# PostgreSQL 服务启动脚本

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
echo "  启动 PostgreSQL 服务"
echo "=========================================="
echo ""

# 检查服务是否已运行
log_info "1. 检查服务状态..."
if ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
    log_success "PostgreSQL 服务已在运行"
    ps aux | grep '[p]ostgres' | grep -v grep | head -3
    exit 0
else
    log_info "服务未运行，准备启动..."
fi
echo ""

# 方法1: 使用 MacPorts 启动
log_info "2. 尝试使用 MacPorts 启动..."
if command -v port &> /dev/null; then
    log_info "执行: sudo port load postgresql${PG_VERSION}-server"
    if sudo port load postgresql${PG_VERSION}-server 2>&1; then
        log_success "启动命令已执行"
        sleep 3
        
        # 检查是否启动成功
        if ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
            log_success "PostgreSQL 服务已成功启动！"
        else
            log_warning "服务可能还在启动中，请稍候..."
            sleep 2
            if ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
                log_success "PostgreSQL 服务已成功启动！"
            else
                log_warning "服务可能启动失败，检查日志..."
            fi
        fi
    else
        log_warning "MacPorts 启动失败，尝试其他方法..."
    fi
else
    log_warning "MacPorts 未安装或不可用"
fi
echo ""

# 方法2: 使用 launchctl 启动
if ! ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
    log_info "3. 尝试使用 launchctl 启动..."
    local plist="/opt/local/Library/LaunchDaemons/org.macports.postgresql${PG_VERSION}-server.plist"
    if [ -f "$plist" ]; then
        log_info "执行: sudo launchctl load -w $plist"
        if sudo launchctl load -w "$plist" 2>&1; then
            log_success "launchctl 启动命令已执行"
            sleep 3
            
            if ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
                log_success "PostgreSQL 服务已成功启动！"
            else
                log_warning "服务可能启动失败"
            fi
        else
            log_warning "launchctl 启动失败"
        fi
    else
        log_info "launchd plist 文件不存在: $plist"
    fi
    echo ""
fi

# 方法3: 手动启动（如果前两种方法都失败）
if ! ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
    log_info "4. 尝试手动启动..."
    local pg_bin="/opt/local/lib/postgresql${PG_VERSION}/bin"
    local pg_data="/opt/local/var/db/postgresql${PG_VERSION}/defaultdb"
    
    if [ -f "$pg_bin/postgres" ] && [ -d "$pg_data" ]; then
        log_warning "前两种方法都失败，需要手动启动"
        log_info "可以使用以下命令手动启动（后台运行）："
        echo ""
        echo "  sudo -u _postgres $pg_bin/postgres -D $pg_data > /tmp/postgres.log 2>&1 &"
        echo ""
        log_info "或者使用 pg_ctl："
        echo "  sudo -u _postgres $pg_bin/pg_ctl -D $pg_data -l /tmp/postgres.log start"
        echo ""
        read -p "是否尝试手动启动? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "启动 PostgreSQL..."
            if sudo -u _postgres "$pg_bin/pg_ctl" -D "$pg_data" -l /tmp/postgres.log start 2>&1; then
                sleep 2
                if ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
                    log_success "PostgreSQL 服务已成功启动！"
                else
                    log_error "启动失败，查看日志: tail -f /tmp/postgres.log"
                fi
            else
                log_error "手动启动失败"
            fi
        fi
    fi
    echo ""
fi

# 最终验证
log_info "5. 最终验证..."
echo ""

if ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
    log_success "✓ PostgreSQL 进程正在运行"
    ps aux | grep '[p]ostgres' | grep -v grep | head -3
    echo ""
    
    if lsof -i :5432 > /dev/null 2>&1; then
        log_success "✓ 端口 5432 正在监听"
        lsof -i :5432 | head -3
        echo ""
    else
        log_warning "✗ 端口 5432 未在监听"
    fi
    
    if [ -S "/tmp/.s.PGSQL.5432" ] || [ -e "/tmp/.s.PGSQL.5432" ]; then
        log_success "✓ 套接字文件存在"
    else
        log_warning "✗ 套接字文件不存在（可能使用 TCP/IP）"
    fi
    echo ""
    
    log_info "6. 测试数据库连接..."
    if sudo -u _postgres psql -d postgres -c "SELECT version();" 2>/dev/null | head -3; then
        log_success "✓ 数据库连接成功！"
        echo ""
        log_info "可以使用以下命令连接："
        echo "  psql -d postgres"
        echo "  或: sudo -u _postgres psql -d postgres"
        echo "  或: psql -h localhost -U _postgres -d postgres"
    else
        log_warning "✗ 数据库连接失败，可能需要配置 pg_hba.conf"
    fi
else
    log_error "PostgreSQL 服务未运行"
    echo ""
    log_info "请检查日志："
    echo "  tail -50 /opt/local/var/log/postgresql${PG_VERSION}/postgresql.log"
    echo "  或: tail -50 /tmp/postgres.log"
    echo ""
    log_info "常见问题："
    echo "  1. 数据目录权限问题"
    echo "  2. 端口被占用"
    echo "  3. 配置文件错误"
fi

echo ""
