#!/bin/bash

# PostgreSQL 完全卸载脚本
# 警告：此脚本将删除所有 PostgreSQL 数据、配置和文件

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
PG_VERSION="${PG_VERSION:-16}"
SKIP_CONFIRM="${SKIP_CONFIRM:-false}"

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

# 显示警告
show_warning() {
    echo ""
    log_error "=========================================="
    log_error "  警告：PostgreSQL 完全卸载"
    log_error "=========================================="
    echo ""
    log_warning "此操作将删除："
    echo "  - PostgreSQL 服务器和客户端"
    echo "  - 所有数据库数据"
    echo "  - 所有配置文件"
    echo "  - 所有日志文件"
    echo "  - 备份文件（如果指定）"
    echo ""
    log_error "此操作不可逆！请确保已备份重要数据！"
    echo ""
}

# 确认操作
confirm_uninstall() {
    if [ "$SKIP_CONFIRM" = "true" ]; then
        return 0
    fi
    
    read -p "确认要完全卸载 PostgreSQL? (输入 'YES' 继续): " confirm
    if [ "$confirm" != "YES" ]; then
        log_info "卸载已取消"
        exit 0
    fi
}

# 清理锁文件和共享内存
cleanup_locks() {
    log_info "清理锁文件和共享内存..."
    
    # 删除 postmaster.pid 文件
    local pid_files=(
        "/opt/local/var/db/postgresql${PG_VERSION}/defaultdb/postmaster.pid"
        "/opt/local/var/db/postgresql/defaultdb/postmaster.pid"
        "/usr/local/var/postgresql${PG_VERSION}/postmaster.pid"
        "/usr/local/var/postgresql/postmaster.pid"
    )
    
    for pid_file in "${pid_files[@]}"; do
        if [ -f "$pid_file" ]; then
            log_info "删除锁文件: $pid_file"
            sudo rm -f "$pid_file" 2>/dev/null || true
        fi
    done
    
    # 清理 Unix 套接字
    local socket_files=(
        "/tmp/.s.PGSQL.5432"
        "/tmp/.s.PGSQL.5432.lock"
        "/opt/local/var/run/postgresql${PG_VERSION}"
    )
    
    for socket in "${socket_files[@]}"; do
        if [ -e "$socket" ]; then
            log_info "删除套接字: $socket"
            sudo rm -rf "$socket" 2>/dev/null || true
        fi
    done
}

# 检查服务是否运行
check_service() {
    log_info "检查 PostgreSQL 服务状态..."
    
    # 更全面的进程检查
    local pg_processes=$(ps aux | grep -E "[p]ostgres|[p]ostmaster" | grep -v grep)
    
    if [ -n "$pg_processes" ]; then
        log_warning "发现以下 PostgreSQL 进程："
        echo "$pg_processes" | while IFS= read -r line; do
            echo "  $line"
        done
        echo ""
        read -p "是否停止这些进程? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            stop_service
        else
            log_error "无法在服务运行时卸载，请先停止服务"
            log_info "可以使用以下命令停止："
            echo "  ./check_postgres_processes.sh --kill"
            exit 1
        fi
    else
        log_info "PostgreSQL 服务未运行"
    fi
}

# 停止服务
stop_service() {
    log_info "停止 PostgreSQL 服务..."
    
    # 尝试使用 MacPorts 停止
    if command -v port &> /dev/null; then
        sudo port unload postgresql${PG_VERSION}-server 2>/dev/null && {
            log_success "MacPorts 服务已停止"
            sleep 2
        }
    fi
    
    # 尝试使用 launchctl
    local launchd_files=(
        "/opt/local/Library/LaunchDaemons/org.macports.postgresql${PG_VERSION}-server.plist"
        "/Library/LaunchDaemons/com.edb.launchd.postgresql-*.plist"
        "/Library/LaunchDaemons/com.postgresql.*.plist"
    )
    
    for plist in "${launchd_files[@]}"; do
        for file in $plist; do
            if [ -f "$file" ]; then
                log_info "卸载 launchd 服务: $file"
                sudo launchctl unload "$file" 2>/dev/null || true
            fi
        done
    done
    
    # 等待服务停止
    sleep 2
    
    # 查找所有 PostgreSQL 相关进程（更全面的搜索）
    log_info "查找所有 PostgreSQL 进程..."
    local pg_pids=$(ps aux | grep -E "[p]ostgres|[p]ostmaster" | grep -v grep | awk '{print $2}' | sort -u)
    
    if [ -n "$pg_pids" ]; then
        log_warning "找到 $pg_pids 个 PostgreSQL 进程，准备终止..."
        
        # 先尝试优雅终止（SIGTERM）
        for pid in $pg_pids; do
            log_info "发送 SIGTERM 到 PID $pid..."
            sudo kill -TERM "$pid" 2>/dev/null || true
        done
        
        # 等待进程结束
        sleep 3
        
        # 检查是否还有进程
        local remaining=$(ps aux | grep -E "[p]ostgres|[p]ostmaster" | grep -v grep | awk '{print $2}' | sort -u)
        
        if [ -n "$remaining" ]; then
            log_warning "仍有进程运行，强制终止..."
            for pid in $remaining; do
                log_info "发送 SIGKILL 到 PID $pid..."
                sudo kill -KILL "$pid" 2>/dev/null || true
            done
            sleep 1
        fi
        
        # 最终检查
        if ps aux | grep -E "[p]ostgres|[p]ostmaster" | grep -v grep > /dev/null; then
            log_error "仍有进程无法终止"
            log_info "请手动检查或重启系统"
            return 1
        else
            log_success "所有进程已停止"
        fi
    else
        log_info "没有找到运行中的 PostgreSQL 进程"
    fi
    
    # 清理锁文件和共享内存
    cleanup_locks
}

# 卸载 MacPorts 包
uninstall_packages() {
    log_info "卸载 PostgreSQL MacPorts 包..."
    
    if ! command -v port &> /dev/null; then
        log_warning "MacPorts 未安装，跳过包卸载"
        return 0
    fi
    
    # 卸载服务器包（会自动卸载客户端包）
    if port installed postgresql${PG_VERSION}-server &> /dev/null; then
        log_info "卸载 postgresql${PG_VERSION}-server..."
        sudo port uninstall postgresql${PG_VERSION}-server 2>/dev/null || {
            log_warning "卸载包时出现问题，继续..."
        }
    fi
    
    # 如果客户端包单独存在，也卸载
    if port installed postgresql${PG_VERSION} &> /dev/null; then
        log_info "卸载 postgresql${PG_VERSION}..."
        sudo port uninstall postgresql${PG_VERSION} 2>/dev/null || {
            log_warning "卸载包时出现问题，继续..."
        }
    fi
    
    log_success "MacPorts 包已卸载"
}

# 删除数据目录
remove_data_directories() {
    log_info "删除数据目录..."
    
    local data_dirs=(
        "/opt/local/var/db/postgresql${PG_VERSION}"
        "/opt/local/var/db/postgresql"
        "/usr/local/var/postgresql${PG_VERSION}"
        "/usr/local/var/postgresql"
        "$HOME/PostgreSQL"
    )
    
    for dir in "${data_dirs[@]}"; do
        if [ -d "$dir" ]; then
            log_info "删除: $dir"
            sudo rm -rf "$dir" 2>/dev/null && log_success "已删除: $dir" || log_warning "删除失败: $dir"
        fi
    done
}

# 删除配置文件
remove_config_files() {
    log_info "删除配置文件..."
    
    local config_dirs=(
        "/opt/local/etc/postgresql${PG_VERSION}"
        "/opt/local/etc/postgresql"
        "/usr/local/etc/postgresql${PG_VERSION}"
        "/usr/local/etc/postgresql"
    )
    
    for dir in "${config_dirs[@]}"; do
        if [ -d "$dir" ]; then
            log_info "删除配置目录: $dir"
            sudo rm -rf "$dir" 2>/dev/null && log_success "已删除: $dir" || log_warning "删除失败: $dir"
        fi
    done
    
    # 删除单独的配置文件
    local config_files=(
        "/opt/local/etc/postgresql.conf"
        "/usr/local/etc/postgresql.conf"
        "$HOME/.pgpass"
        "$HOME/.psqlrc"
    )
    
    for file in "${config_files[@]}"; do
        if [ -f "$file" ]; then
            log_info "删除配置文件: $file"
            rm -f "$file" 2>/dev/null && log_success "已删除: $file" || log_warning "删除失败: $file"
        fi
    done
}

# 删除日志文件
remove_log_files() {
    log_info "删除日志文件..."
    
    local log_dirs=(
        "/opt/local/var/log/postgresql${PG_VERSION}"
        "/opt/local/var/log/postgresql"
        "/usr/local/var/log/postgresql${PG_VERSION}"
        "/usr/local/var/log/postgresql"
    )
    
    for dir in "${log_dirs[@]}"; do
        if [ -d "$dir" ]; then
            log_info "删除日志目录: $dir"
            sudo rm -rf "$dir" 2>/dev/null && log_success "已删除: $dir" || log_warning "删除失败: $dir"
        fi
    done
}

# 删除可执行文件（如果存在）
remove_binaries() {
    log_info "检查残留的可执行文件..."
    
    local bin_dirs=(
        "/opt/local/lib/postgresql${PG_VERSION}/bin"
        "/opt/local/lib/postgresql/bin"
        "/usr/local/lib/postgresql${PG_VERSION}/bin"
        "/usr/local/lib/postgresql/bin"
    )
    
    for dir in "${bin_dirs[@]}"; do
        if [ -d "$dir" ]; then
            log_info "删除可执行文件目录: $dir"
            sudo rm -rf "$dir" 2>/dev/null && log_success "已删除: $dir" || log_warning "删除失败: $dir"
        fi
    done
}

# 删除 _postgres 用户（可选）
remove_postgres_user() {
    log_info "检查 _postgres 用户..."
    
    if id "_postgres" &>/dev/null; then
        read -p "是否删除 _postgres 用户? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "删除 _postgres 用户..."
            sudo dscl . -delete /Users/_postgres 2>/dev/null && {
                log_success "_postgres 用户已删除"
            } || {
                log_warning "删除用户失败（可能不存在或正在使用）"
            }
        fi
    else
        log_info "_postgres 用户不存在，跳过"
    fi
}

# 清理环境变量
cleanup_environment() {
    log_info "清理环境变量..."
    
    local shell_configs=(
        "$HOME/.zprofile"
        "$HOME/.zshrc"
        "$HOME/.bash_profile"
        "$HOME/.bashrc"
    )
    
    for config_file in "${shell_configs[@]}"; do
        if [ -f "$config_file" ]; then
            # 备份配置文件
            cp "$config_file" "${config_file}.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
            
            # 删除 PostgreSQL 相关环境变量
            if grep -q "postgresql" "$config_file" 2>/dev/null; then
                log_info "清理 $config_file 中的 PostgreSQL 环境变量..."
                sed -i.bak '/postgresql/d' "$config_file" 2>/dev/null || {
                    # macOS sed 需要备份文件
                    sed -i '' '/postgresql/d' "$config_file" 2>/dev/null || true
                }
                log_success "已清理 $config_file"
            fi
        fi
    done
}

# 删除备份文件（可选）
remove_backup_files() {
    read -p "是否删除备份文件? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        local backup_dirs=(
            "/backup/postgresql"
            "$HOME/backup/postgresql"
        )
        
        for dir in "${backup_dirs[@]}"; do
            if [ -d "$dir" ]; then
                log_info "删除备份目录: $dir"
                read -p "确认删除 $dir? (y/n): " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    sudo rm -rf "$dir" 2>/dev/null && log_success "已删除: $dir" || log_warning "删除失败: $dir"
                fi
            fi
        done
    fi
}

# 验证卸载
verify_uninstall() {
    log_info "验证卸载..."
    
    local found=false
    
    # 检查进程
    if ps aux | grep -E "[p]ostgres" > /dev/null; then
        log_warning "仍有 PostgreSQL 进程在运行"
        found=true
    fi
    
    # 检查命令
    if command -v psql &> /dev/null; then
        log_warning "psql 命令仍可用: $(which psql)"
        found=true
    fi
    
    # 检查数据目录
    if [ -d "/opt/local/var/db/postgresql${PG_VERSION}" ] || [ -d "/usr/local/var/postgresql${PG_VERSION}" ]; then
        log_warning "数据目录仍存在"
        found=true
    fi
    
    if [ "$found" = false ]; then
        log_success "PostgreSQL 已完全卸载"
    else
        log_warning "部分文件或进程可能仍存在，请手动检查"
    fi
}

# 显示使用说明
show_usage() {
    echo "PostgreSQL 完全卸载脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --version <version>   PostgreSQL 版本（默认: 16）"
    echo "  --skip-confirm        跳过确认提示"
    echo "  --help                显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 交互式卸载"
    echo "  $0 --version 15       # 卸载 PostgreSQL 15"
    echo "  $0 --skip-confirm     # 非交互式卸载（危险）"
}

# 主函数
main() {
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --version)
                PG_VERSION="$2"
                shift 2
                ;;
            --skip-confirm)
                SKIP_CONFIRM=true
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # 显示警告
    show_warning
    
    # 确认操作
    confirm_uninstall
    
    # 检查服务
    check_service
    
    # 停止服务
    stop_service
    
    # 卸载包
    uninstall_packages
    
    # 删除数据目录
    remove_data_directories
    
    # 删除配置文件
    remove_config_files
    
    # 删除日志文件
    remove_log_files
    
    # 删除可执行文件
    remove_binaries
    
    # 删除用户（可选）
    remove_postgres_user
    
    # 清理环境变量
    cleanup_environment
    
    # 删除备份文件（可选）
    remove_backup_files
    
    # 验证卸载
    verify_uninstall
    
    echo ""
    log_success "卸载完成！"
    log_info "建议重新打开终端以使环境变量更改生效"
}

# 运行主函数
main "$@"
