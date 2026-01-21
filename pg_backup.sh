#!/bin/bash

# PostgreSQL 备份脚本
# 支持每日、每周、每月备份
# 使用方法: ./pg_backup.sh [daily|weekly|monthly] [database_name]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量（从环境变量或默认值）
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-_postgres}"
PG_BACKUP_BASE="${PG_BACKUP_BASE:-/backup/postgresql}"
PG_DUMP_OPTIONS="${PG_DUMP_OPTIONS:--Fc}"  # 自定义格式，支持压缩
COMPRESS="${COMPRESS:-true}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
RETENTION_WEEKS="${RETENTION_WEEKS:-4}"
RETENTION_MONTHS="${RETENTION_MONTHS:-12}"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 命令未找到"
        exit 1
    fi
}

# 检查 PostgreSQL 连接
check_connection() {
    log_info "检查 PostgreSQL 连接..."
    if sudo su "$PG_USER" -c "psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d postgres -c 'SELECT version();'" &> /dev/null; then
        log_success "PostgreSQL 连接正常"
    else
        log_error "无法连接到 PostgreSQL"
        exit 1
    fi
}

# 创建备份目录
create_backup_dir() {
    local backup_type=$1
    local backup_path="$PG_BACKUP_BASE/$backup_type"
    
    if [ ! -d "$backup_path" ]; then
        log_info "创建备份目录: $backup_path"
        sudo mkdir -p "$backup_path"
        sudo chmod 700 "$backup_path"
    fi
}

# 备份单个数据库
backup_database() {
    local db_name=$1
    local backup_type=$2
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    
    # 确定备份路径
    local backup_dir
    case $backup_type in
        daily)
            backup_dir="$PG_BACKUP_BASE/daily/$(date '+%Y-%m-%d')"
            ;;
        weekly)
            backup_dir="$PG_BACKUP_BASE/weekly/$(date '+%Y-W%V')"
            ;;
        monthly)
            backup_dir="$PG_BACKUP_BASE/monthly/$(date '+%Y-%m')"
            ;;
        *)
            log_error "未知的备份类型: $backup_type"
            exit 1
            ;;
    esac
    
    # 创建备份目录
    sudo mkdir -p "$backup_dir"
    sudo chmod 700 "$backup_dir"
    
    local backup_file="$backup_dir/${db_name}_${timestamp}.dump"
    
    log_info "备份数据库: $db_name"
    log_info "备份文件: $backup_file"
    
    # 执行备份
    if sudo su "$PG_USER" -c "pg_dump -h $PG_HOST -p $PG_PORT -U $PG_USER -d $db_name $PG_DUMP_OPTIONS -f $backup_file" 2>&1; then
        # 设置文件权限
        sudo chmod 600 "$backup_file"
        sudo chown "$PG_USER:$PG_USER" "$backup_file"
        
        # 获取文件大小
        local file_size=$(sudo stat -f%z "$backup_file" 2>/dev/null || sudo stat -c%s "$backup_file" 2>/dev/null)
        local file_size_mb=$((file_size / 1024 / 1024))
        
        log_success "数据库 $db_name 备份完成 (${file_size_mb} MB)"
        
        # 如果启用压缩且不是自定义格式，进行压缩
        if [ "$COMPRESS" = "true" ] && [[ ! "$PG_DUMP_OPTIONS" =~ -Fc ]]; then
            log_info "压缩备份文件..."
            sudo gzip "$backup_file"
            backup_file="${backup_file}.gz"
            file_size=$(sudo stat -f%z "$backup_file" 2>/dev/null || sudo stat -c%s "$backup_file" 2>/dev/null)
            file_size_mb=$((file_size / 1024 / 1024))
            log_success "压缩完成 (${file_size_mb} MB)"
        fi
        
        echo "$backup_file"
    else
        log_error "数据库 $db_name 备份失败"
        return 1
    fi
}

# 备份所有数据库
backup_all_databases() {
    local backup_type=$1
    
    log_info "获取数据库列表..."
    local databases=$(sudo su "$PG_USER" -c "psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d postgres -t -c \"SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres';\"" | tr -d ' ')
    
    if [ -z "$databases" ]; then
        log_warning "没有找到需要备份的数据库"
        return 0
    fi
    
    local success_count=0
    local fail_count=0
    
    for db in $databases; do
        if backup_database "$db" "$backup_type"; then
            ((success_count++))
        else
            ((fail_count++))
        fi
    done
    
    log_info "备份完成: 成功 $success_count, 失败 $fail_count"
    
    if [ $fail_count -gt 0 ]; then
        return 1
    fi
}

# 清理旧备份
cleanup_old_backups() {
    local backup_type=$1
    local retention_days=$2
    
    log_info "清理 $backup_type 类型的旧备份（保留 $retention_days 天）..."
    
    local backup_dir="$PG_BACKUP_BASE/$backup_type"
    
    if [ ! -d "$backup_dir" ]; then
        return 0
    fi
    
    # 查找并删除旧备份
    local deleted_count=0
    while IFS= read -r -d '' old_backup; do
        log_info "删除旧备份: $old_backup"
        sudo rm -rf "$old_backup"
        ((deleted_count++))
    done < <(find "$backup_dir" -type d -mtime +$retention_days -print0 2>/dev/null || true)
    
    if [ $deleted_count -gt 0 ]; then
        log_success "已删除 $deleted_count 个旧备份"
    else
        log_info "没有需要删除的旧备份"
    fi
}

# 生成备份报告
generate_report() {
    local backup_type=$1
    local report_file="$PG_BACKUP_BASE/${backup_type}_report_$(date '+%Y%m%d').txt"
    
    log_info "生成备份报告: $report_file"
    
    {
        echo "PostgreSQL 备份报告"
        echo "==================="
        echo "备份类型: $backup_type"
        echo "备份时间: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "主机: $PG_HOST:$PG_PORT"
        echo "用户: $PG_USER"
        echo ""
        echo "备份文件列表:"
        find "$PG_BACKUP_BASE/$backup_type" -type f -name "*.dump*" -exec ls -lh {} \; 2>/dev/null | awk '{print $9, $5}'
        echo ""
        echo "磁盘使用情况:"
        df -h "$PG_BACKUP_BASE" | tail -1
    } | sudo tee "$report_file" > /dev/null
    
    sudo chmod 600 "$report_file"
    log_success "备份报告已生成"
}

# 主函数
main() {
    local backup_type=${1:-daily}
    local db_name=${2:-""}
    
    # 验证备份类型
    case $backup_type in
        daily|weekly|monthly)
            ;;
        *)
            log_error "无效的备份类型: $backup_type"
            echo "使用方法: $0 [daily|weekly|monthly] [database_name]"
            exit 1
            ;;
    esac
    
    log_info "开始 $backup_type 备份..."
    
    # 检查必要的命令
    check_command psql
    check_command pg_dump
    
    # 检查连接
    check_connection
    
    # 创建备份目录
    create_backup_dir "$backup_type"
    
    # 执行备份
    if [ -n "$db_name" ]; then
        # 备份指定数据库
        backup_database "$db_name" "$backup_type"
    else
        # 备份所有数据库
        backup_all_databases "$backup_type"
    fi
    
    # 清理旧备份
    case $backup_type in
        daily)
            cleanup_old_backups daily "$RETENTION_DAYS"
            ;;
        weekly)
            cleanup_old_backups weekly $((RETENTION_WEEKS * 7))
            ;;
        monthly)
            cleanup_old_backups monthly $((RETENTION_MONTHS * 30))
            ;;
    esac
    
    # 生成报告
    generate_report "$backup_type"
    
    log_success "$backup_type 备份完成！"
}

# 运行主函数
main "$@"
