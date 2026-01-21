#!/bin/bash

# PostgreSQL 进程检查脚本
# 用于诊断和清理残留的 PostgreSQL 进程

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 查找所有 PostgreSQL 相关进程
find_postgres_processes() {
    log_info "查找所有 PostgreSQL 相关进程..."
    echo ""
    
    # 使用多种方式查找进程
    local processes=$(ps aux | grep -E "[p]ostgres|postmaster" | grep -v grep)
    
    if [ -z "$processes" ]; then
        log_success "没有找到 PostgreSQL 进程"
        return 0
    fi
    
    log_warning "找到以下 PostgreSQL 进程："
    echo ""
    echo "$processes" | while IFS= read -r line; do
        local pid=$(echo "$line" | awk '{print $2}')
        local user=$(echo "$line" | awk '{print $1}')
        local cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        
        echo "  PID: $pid | 用户: $user | 命令: $cmd"
    done
    echo ""
    
    return 1
}

# 显示进程详细信息
show_process_details() {
    log_info "进程详细信息："
    echo ""
    
    ps aux | grep -E "[p]ostgres|postmaster" | grep -v grep | while IFS= read -r line; do
        local pid=$(echo "$line" | awk '{print $2}')
        
        echo "进程 PID: $pid"
        echo "完整命令行:"
        ps -p "$pid" -o command= 2>/dev/null || echo "  无法获取（进程可能已结束）"
        echo ""
        
        # 显示进程树
        echo "进程树:"
        pstree -p "$pid" 2>/dev/null || ps -p "$pid" -o pid,ppid,cmd 2>/dev/null || echo "  无法获取"
        echo ""
        
        # 显示打开的文件
        echo "打开的文件:"
        lsof -p "$pid" 2>/dev/null | head -10 || echo "  无法获取或需要权限"
        echo "---"
    done
}

# 检查进程来源
check_process_source() {
    log_info "检查进程来源..."
    echo ""
    
    ps aux | grep -E "[p]ostgres|postmaster" | grep -v grep | while IFS= read -r line; do
        local pid=$(echo "$line" | awk '{print $2}')
        local cmd=$(ps -p "$pid" -o command= 2>/dev/null)
        
        if [ -z "$cmd" ]; then
            continue
        fi
        
        echo "PID $pid:"
        
        # 检查是否来自 MacPorts
        if echo "$cmd" | grep -q "/opt/local"; then
            echo "  来源: MacPorts"
            echo "  路径: $(echo "$cmd" | grep -o '/opt/local[^ ]*' | head -1)"
        fi
        
        # 检查是否来自 Homebrew
        if echo "$cmd" | grep -q "/opt/homebrew\|/usr/local"; then
            echo "  来源: Homebrew 或手动安装"
            echo "  路径: $(echo "$cmd" | grep -o '/opt/homebrew[^ ]*\|/usr/local[^ ]*' | head -1)"
        fi
        
        # 检查数据目录
        local data_dir=$(echo "$cmd" | grep -o '\-D [^ ]*' | awk '{print $2}')
        if [ -n "$data_dir" ]; then
            echo "  数据目录: $data_dir"
            if [ -d "$data_dir" ]; then
                echo "  数据目录存在: 是"
            else
                echo "  数据目录存在: 否（可能已删除）"
            fi
        fi
        
        echo ""
    done
}

# 检查服务状态
check_service_status() {
    log_info "检查服务状态..."
    echo ""
    
    # MacPorts
    if command -v port &> /dev/null; then
        log_info "MacPorts 服务状态:"
        port installed | grep postgresql || echo "  未安装 PostgreSQL 包"
        echo ""
        
        # 检查 launchd 服务
        if [ -f "/opt/local/Library/LaunchDaemons/org.macports.postgresql16-server.plist" ]; then
            log_info "LaunchDaemon 文件存在:"
            echo "  /opt/local/Library/LaunchDaemons/org.macports.postgresql16-server.plist"
            launchctl list | grep postgresql || echo "  服务未加载"
        fi
        echo ""
    fi
    
    # Homebrew
    if command -v brew &> /dev/null; then
        log_info "Homebrew 服务状态:"
        brew services list | grep postgresql || echo "  未通过 Homebrew 安装 PostgreSQL"
        echo ""
    fi
    
    # launchd
    log_info "系统 launchd 服务:"
    launchctl list | grep -i postgres || echo "  没有找到 PostgreSQL 相关的 launchd 服务"
    echo ""
}

# 终止进程
kill_processes() {
    log_warning "准备终止所有 PostgreSQL 进程..."
    
    read -p "确认终止所有进程? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "已取消"
        return 0
    fi
    
    # 获取所有进程 PID
    local pids=$(ps aux | grep -E "[p]ostgres|postmaster" | awk '{print $2}')
    
    if [ -z "$pids" ]; then
        log_info "没有找到需要终止的进程"
        return 0
    fi
    
    log_info "终止进程..."
    
    # 先尝试优雅终止（SIGTERM）
    for pid in $pids; do
        log_info "发送 SIGTERM 到 PID $pid..."
        sudo kill -TERM "$pid" 2>/dev/null || true
    done
    
    # 等待进程结束
    sleep 3
    
    # 检查是否还有进程
    local remaining=$(ps aux | grep -E "[p]ostgres|postmaster" | grep -v grep | awk '{print $2}')
    
    if [ -n "$remaining" ]; then
        log_warning "仍有进程运行，强制终止..."
        for pid in $remaining; do
            log_info "发送 SIGKILL 到 PID $pid..."
            sudo kill -KILL "$pid" 2>/dev/null || true
        done
        sleep 1
    fi
    
    # 最终检查
    if ps aux | grep -E "[p]ostgres|postmaster" | grep -v grep > /dev/null; then
        log_error "仍有进程无法终止，可能需要重启系统"
        return 1
    else
        log_success "所有进程已终止"
        return 0
    fi
}

# 清理残留
cleanup_residuals() {
    log_info "清理残留文件和锁..."
    
    # 查找并删除锁文件
    local lock_files=(
        "/opt/local/var/db/postgresql16/defaultdb/postmaster.pid"
        "/usr/local/var/postgresql16/postmaster.pid"
        "/tmp/.s.PGSQL.5432*"
    )
    
    for pattern in "${lock_files[@]}"; do
        for file in $pattern; do
            if [ -f "$file" ]; then
                log_info "删除锁文件: $file"
                sudo rm -f "$file" 2>/dev/null || true
            fi
        done
    done
    
    # 清理共享内存
    log_info "检查共享内存..."
    ipcs -m | grep _postgres || log_info "没有找到 PostgreSQL 共享内存"
    
    log_success "清理完成"
}

# 显示使用说明
show_usage() {
    echo "PostgreSQL 进程检查脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --check              检查进程（默认）"
    echo "  --details            显示详细信息"
    echo "  --source             检查进程来源"
    echo "  --service            检查服务状态"
    echo "  --kill               终止所有进程"
    echo "  --cleanup            清理残留文件"
    echo "  --all                执行所有检查"
    echo "  --help               显示此帮助"
    echo ""
    echo "示例:"
    echo "  $0                   # 基本检查"
    echo "  $0 --all             # 完整检查"
    echo "  $0 --kill            # 终止所有进程"
}

# 主函数
main() {
    local check_only=false
    local show_details=false
    local check_source=false
    local check_service=false
    local kill_procs=false
    local cleanup=false
    local all=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --check)
                check_only=true
                shift
                ;;
            --details)
                show_details=true
                shift
                ;;
            --source)
                check_source=true
                shift
                ;;
            --service)
                check_service=true
                shift
                ;;
            --kill)
                kill_procs=true
                shift
                ;;
            --cleanup)
                cleanup=true
                shift
                ;;
            --all)
                all=true
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
    
    # 如果没有指定选项，默认检查
    if [ "$all" = false ] && [ "$check_only" = false ] && [ "$show_details" = false ] && \
       [ "$check_source" = false ] && [ "$check_service" = false ] && \
       [ "$kill_procs" = false ] && [ "$cleanup" = false ]; then
        check_only=true
    fi
    
    echo "=========================================="
    echo "  PostgreSQL 进程检查工具"
    echo "=========================================="
    echo ""
    
    # 执行检查
    if [ "$all" = true ] || [ "$check_only" = true ]; then
        find_postgres_processes
        echo ""
    fi
    
    if [ "$all" = true ] || [ "$show_details" = true ]; then
        show_process_details
    fi
    
    if [ "$all" = true ] || [ "$check_source" = true ]; then
        check_process_source
    fi
    
    if [ "$all" = true ] || [ "$check_service" = true ]; then
        check_service_status
    fi
    
    if [ "$kill_procs" = true ]; then
        kill_processes
    fi
    
    if [ "$cleanup" = true ]; then
        cleanup_residuals
    fi
}

# 运行主函数
main "$@"
