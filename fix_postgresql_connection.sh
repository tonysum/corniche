#!/bin/bash

# PostgreSQL 连接问题修复脚本
# 解决 "connection to server socket" 错误

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
PG_VERSION="${PG_VERSION:-15}"

# 日志函数
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

# 检查服务是否运行
check_service_running() {
    log_info "检查 PostgreSQL 服务状态..."
    
    # 检查进程
    if ps aux | grep -E "[p]ostgres.*postmaster" > /dev/null; then
        log_success "PostgreSQL 进程正在运行"
        return 0
    else
        log_warning "PostgreSQL 进程未运行"
        return 1
    fi
}

# 检查套接字文件
check_socket_files() {
    log_info "检查套接字文件..."
    
    local socket_locations=(
        "/tmp/.s.PGSQL.5432"
        "/tmp/.s.PGSQL.5432.lock"
        "/opt/local/var/run/postgresql${PG_VERSION}/.s.PGSQL.5432"
        "/usr/local/var/run/postgresql${PG_VERSION}/.s.PGSQL.5432"
        "/var/run/postgresql/.s.PGSQL.5432"
    )
    
    local found=false
    for socket in "${socket_locations[@]}"; do
        if [ -S "$socket" ] || [ -e "$socket" ]; then
            log_info "找到套接字文件: $socket"
            found=true
        fi
    done
    
    if [ "$found" = false ]; then
        log_warning "未找到套接字文件"
    fi
    
    return 0
}

# 检查端口监听
check_port_listening() {
    log_info "检查端口 5432 是否在监听..."
    
    if lsof -i :5432 > /dev/null 2>&1; then
        log_success "端口 5432 正在监听"
        lsof -i :5432
        return 0
    else
        log_warning "端口 5432 未在监听"
        return 1
    fi
}

# 检查配置文件
check_config_file() {
    log_info "检查 PostgreSQL 配置文件..."
    
    local config_files=(
        "/opt/local/etc/postgresql${PG_VERSION}/postgresql.conf"
        "/opt/local/var/db/postgresql${PG_VERSION}/defaultdb/postgresql.conf"
        "/usr/local/etc/postgresql${PG_VERSION}/postgresql.conf"
    )
    
    local config_file=""
    for file in "${config_files[@]}"; do
        if [ -f "$file" ]; then
            config_file="$file"
            log_info "找到配置文件: $file"
            break
        fi
    done
    
    if [ -z "$config_file" ]; then
        log_warning "未找到配置文件"
        return 1
    fi
    
    # 检查 unix_socket_directories 设置
    log_info "检查 unix_socket_directories 设置..."
    if grep -q "^unix_socket_directories" "$config_file" 2>/dev/null; then
        local socket_dirs=$(grep "^unix_socket_directories" "$config_file" | cut -d"'" -f2)
        log_info "unix_socket_directories = $socket_dirs"
    else
        log_info "未设置 unix_socket_directories（使用默认值）"
    fi
    
    # 检查 port 设置
    log_info "检查 port 设置..."
    if grep -q "^port" "$config_file" 2>/dev/null; then
        local port=$(grep "^port" "$config_file" | awk '{print $3}' | head -1)
        log_info "port = $port"
    else
        log_info "未设置 port（使用默认值 5432）"
    fi
    
    return 0
}

# 启动服务
start_service() {
    log_info "启动 PostgreSQL 服务..."
    
    # 尝试使用 MacPorts 启动
    if command -v port &> /dev/null; then
        log_info "使用 MacPorts 启动服务..."
        if sudo port load postgresql${PG_VERSION}-server 2>/dev/null; then
            log_success "服务启动命令已执行"
            sleep 3
            
            # 检查是否成功启动
            if check_service_running; then
                log_success "PostgreSQL 服务已成功启动"
                return 0
            fi
        fi
    fi
    
    # 尝试使用 launchctl
    local plist="/opt/local/Library/LaunchDaemons/org.macports.postgresql${PG_VERSION}-server.plist"
    if [ -f "$plist" ]; then
        log_info "使用 launchctl 启动服务..."
        if sudo launchctl load -w "$plist" 2>/dev/null; then
            log_success "服务启动命令已执行"
            sleep 3
            
            if check_service_running; then
                log_success "PostgreSQL 服务已成功启动"
                return 0
            fi
        fi
    fi
    
    # 尝试手动启动
    log_info "尝试手动启动 PostgreSQL..."
    local pg_bin="/opt/local/lib/postgresql${PG_VERSION}/bin"
    local pg_data="/opt/local/var/db/postgresql${PG_VERSION}/defaultdb"
    
    if [ -f "$pg_bin/postgres" ] && [ -d "$pg_data" ]; then
        log_info "使用 postgres 命令启动..."
        log_warning "这将在前台运行，按 Ctrl+C 停止"
        log_info "命令: sudo su _postgres -c '$pg_bin/postgres -D $pg_data'"
        log_info "建议使用后台方式启动服务"
    fi
    
    log_error "无法自动启动服务"
    return 1
}

# 修复套接字配置
fix_socket_config() {
    log_info "修复套接字配置..."
    
    local config_file=""
    local config_files=(
        "/opt/local/etc/postgresql${PG_VERSION}/postgresql.conf"
        "/opt/local/var/db/postgresql${PG_VERSION}/defaultdb/postgresql.conf"
    )
    
    for file in "${config_files[@]}"; do
        if [ -f "$file" ]; then
            config_file="$file"
            break
        fi
    done
    
    if [ -z "$config_file" ]; then
        log_error "未找到配置文件"
        return 1
    fi
    
    # 备份配置文件
    sudo cp "$config_file" "${config_file}.backup.$(date +%Y%m%d_%H%M%S)"
    
    # 检查并设置 unix_socket_directories
    if ! grep -q "^unix_socket_directories" "$config_file" 2>/dev/null; then
        log_info "添加 unix_socket_directories 配置..."
        echo "" | sudo tee -a "$config_file" > /dev/null
        echo "# Unix socket directories" | sudo tee -a "$config_file" > /dev/null
        echo "unix_socket_directories = '/tmp'" | sudo tee -a "$config_file" > /dev/null
        log_success "已添加 unix_socket_directories = '/tmp'"
    else
        log_info "unix_socket_directories 已存在，检查是否需要修改..."
        # 可以在这里添加修改逻辑
    fi
    
    return 0
}

# 创建套接字目录
create_socket_directory() {
    log_info "创建套接字目录..."
    
    local socket_dirs=(
        "/tmp"
        "/opt/local/var/run/postgresql${PG_VERSION}"
    )
    
    for dir in "${socket_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            log_info "创建目录: $dir"
            sudo mkdir -p "$dir"
            sudo chmod 1777 "$dir"  # 设置 sticky bit
        fi
    done
    
    # 确保 /tmp 权限正确
    if [ -d "/tmp" ]; then
        sudo chmod 1777 /tmp
        log_success "套接字目录已准备就绪"
    fi
}

# 测试连接
test_connection() {
    log_info "测试 PostgreSQL 连接..."
    
    # 方法1: 使用 Unix 套接字
    log_info "方法1: 使用 Unix 套接字连接..."
    if sudo su _postgres -c "psql -d postgres -c 'SELECT version();'" 2>/dev/null; then
        log_success "Unix 套接字连接成功"
        return 0
    fi
    
    # 方法2: 使用 TCP/IP
    log_info "方法2: 使用 TCP/IP 连接..."
    if sudo su _postgres -c "psql -h localhost -d postgres -c 'SELECT version();'" 2>/dev/null; then
        log_success "TCP/IP 连接成功"
        return 0
    fi
    
    # 方法3: 指定套接字路径
    log_info "方法3: 尝试不同的套接字路径..."
    for socket_dir in "/tmp" "/opt/local/var/run/postgresql${PG_VERSION}"; do
        if [ -d "$socket_dir" ]; then
            if sudo su _postgres -c "psql -h $socket_dir -d postgres -c 'SELECT version();'" 2>/dev/null; then
                log_success "使用路径 $socket_dir 连接成功"
                return 0
            fi
        fi
    done
    
    log_error "所有连接方法都失败"
    return 1
}

# 显示诊断信息
show_diagnosis() {
    echo ""
    log_info "=========================================="
    log_info "  PostgreSQL 连接诊断"
    log_info "=========================================="
    echo ""
    
    check_service_running
    echo ""
    
    check_socket_files
    echo ""
    
    check_port_listening
    echo ""
    
    check_config_file
    echo ""
}

# 显示解决方案
show_solutions() {
    echo ""
    log_info "=========================================="
    log_info "  解决方案"
    log_info "=========================================="
    echo ""
    
    log_info "1. 启动 PostgreSQL 服务："
    echo "   sudo port load postgresql${PG_VERSION}-server"
    echo ""
    
    log_info "2. 检查服务状态："
    echo "   sudo port installed postgresql${PG_VERSION}-server"
    echo "   ps aux | grep postgres"
    echo ""
    
    log_info "3. 使用 TCP/IP 连接（如果 Unix 套接字不可用）："
    echo "   psql -h localhost -U _postgres -d postgres"
    echo ""
    
    log_info "4. 检查配置文件："
    echo "   sudo cat /opt/local/etc/postgresql${PG_VERSION}/postgresql.conf | grep -E 'unix_socket|port'"
    echo ""
    
    log_info "5. 查看日志："
    echo "   tail -f /opt/local/var/log/postgresql${PG_VERSION}/postgresql.log"
    echo ""
}

# 主函数
main() {
    local auto_fix=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --fix)
                auto_fix=true
                shift
                ;;
            --version)
                PG_VERSION="$2"
                shift 2
                ;;
            --help|-h)
                echo "PostgreSQL 连接问题修复脚本"
                echo ""
                echo "使用方法:"
                echo "  $0 [选项]"
                echo ""
                echo "选项:"
                echo "  --fix           自动尝试修复"
                echo "  --version <ver>  PostgreSQL 版本（默认: 15）"
                echo "  --help          显示帮助"
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                exit 1
                ;;
        esac
    done
    
    # 显示诊断信息
    show_diagnosis
    
    # 如果服务未运行
    if ! check_service_running; then
        log_warning "PostgreSQL 服务未运行"
        
        if [ "$auto_fix" = true ]; then
            read -p "是否启动服务? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                start_service
                sleep 2
            fi
        else
            log_info "使用 --fix 选项可以自动启动服务"
        fi
    fi
    
    # 如果自动修复
    if [ "$auto_fix" = true ]; then
        log_info "执行自动修复..."
        
        # 创建套接字目录
        create_socket_directory
        
        # 修复配置
        fix_socket_config
        
        # 如果服务未运行，尝试启动
        if ! check_service_running; then
            start_service
        fi
        
        # 等待服务启动
        sleep 3
        
        # 测试连接
        test_connection
    fi
    
    # 显示解决方案
    show_solutions
}

# 运行主函数
main "$@"
