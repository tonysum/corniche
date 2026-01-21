#!/bin/bash

# PostgreSQL 恢复脚本
# 使用方法: ./pg_restore.sh <backup_file> [target_database] [options]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-_postgres}"

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

# 显示使用说明
show_usage() {
    echo "PostgreSQL 恢复脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 <backup_file> [target_database] [options]"
    echo ""
    echo "参数:"
    echo "  backup_file      备份文件路径（.dump 或 .sql）"
    echo "  target_database  目标数据库名（可选，默认从备份文件推断）"
    echo ""
    echo "选项:"
    echo "  --create-db      创建数据库（如果不存在）"
    echo "  --clean          恢复前清理数据库对象"
    echo "  --if-exists       使用 IF EXISTS 选项"
    echo "  --no-owner       不恢复所有权"
    echo "  --no-privileges  不恢复权限"
    echo "  --list           仅列出备份内容，不恢复"
    echo ""
    echo "示例:"
    echo "  $0 /backup/postgresql/daily/2025-01-15/crypto_data_20250115_020000.dump crypto_data"
    echo "  $0 /backup/postgresql/daily/2025-01-15/crypto_data_20250115_020000.dump crypto_data --create-db --clean"
    echo "  $0 /backup/postgresql/daily/2025-01-15/crypto_data_20250115_020000.dump --list"
}

# 检查备份文件
check_backup_file() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi
    
    # 检查文件类型
    if [[ "$backup_file" == *.dump ]] || [[ "$backup_file" == *.dump.gz ]]; then
        log_info "检测到自定义格式备份文件"
        return 0
    elif [[ "$backup_file" == *.sql ]] || [[ "$backup_file" == *.sql.gz ]]; then
        log_info "检测到 SQL 格式备份文件"
        return 0
    else
        log_warning "未知的备份文件格式，尝试自动检测..."
        return 0
    fi
}

# 列出备份内容
list_backup_content() {
    local backup_file=$1
    
    log_info "列出备份内容..."
    
    if [[ "$backup_file" == *.dump ]] || [[ "$backup_file" == *.dump.gz ]]; then
        # 自定义格式
        if [[ "$backup_file" == *.gz ]]; then
            gunzip -c "$backup_file" | sudo su "$PG_USER" -c "pg_restore -l -" 2>/dev/null || \
            sudo su "$PG_USER" -c "pg_restore -l $backup_file" 2>/dev/null
        else
            sudo su "$PG_USER" -c "pg_restore -l $backup_file" 2>/dev/null
        fi
    else
        log_warning "SQL 格式备份无法列出内容，将直接恢复"
    fi
}

# 恢复数据库
restore_database() {
    local backup_file=$1
    local target_db=$2
    shift 2
    local restore_options="$@"
    
    log_info "开始恢复数据库..."
    log_info "备份文件: $backup_file"
    log_info "目标数据库: $target_db"
    
    # 检查数据库是否存在
    local db_exists=$(sudo su "$PG_USER" -c "psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d postgres -t -c \"SELECT 1 FROM pg_database WHERE datname = '$target_db';\"" | tr -d ' ')
    
    if [ -z "$db_exists" ]; then
        if [[ "$restore_options" == *"--create-db"* ]]; then
            log_info "创建数据库: $target_db"
            sudo su "$PG_USER" -c "psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d postgres -c \"CREATE DATABASE $target_db;\"" || {
                log_error "创建数据库失败"
                exit 1
            }
        else
            log_error "数据库 $target_db 不存在，使用 --create-db 选项创建"
            exit 1
        fi
    fi
    
    # 执行恢复
    if [[ "$backup_file" == *.dump ]] || [[ "$backup_file" == *.dump.gz ]]; then
        # 自定义格式
        log_info "使用 pg_restore 恢复..."
        
        local pg_restore_cmd="pg_restore -h $PG_HOST -p $PG_PORT -U $PG_USER -d $target_db"
        
        # 添加选项
        if [[ "$restore_options" == *"--clean"* ]]; then
            pg_restore_cmd="$pg_restore_cmd --clean"
        fi
        if [[ "$restore_options" == *"--if-exists"* ]]; then
            pg_restore_cmd="$pg_restore_cmd --if-exists"
        fi
        if [[ "$restore_options" == *"--no-owner"* ]]; then
            pg_restore_cmd="$pg_restore_cmd --no-owner"
        fi
        if [[ "$restore_options" == *"--no-privileges"* ]]; then
            pg_restore_cmd="$pg_restore_cmd --no-privileges"
        fi
        
        if [[ "$backup_file" == *.gz ]]; then
            # 解压并恢复
            gunzip -c "$backup_file" | sudo su "$PG_USER" -c "$pg_restore_cmd -" || {
                log_error "恢复失败"
                exit 1
            }
        else
            sudo su "$PG_USER" -c "$pg_restore_cmd $backup_file" || {
                log_error "恢复失败"
                exit 1
            }
        fi
    else
        # SQL 格式
        log_info "使用 psql 恢复..."
        
        if [[ "$backup_file" == *.gz ]]; then
            gunzip -c "$backup_file" | sudo su "$PG_USER" -c "psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $target_db" || {
                log_error "恢复失败"
                exit 1
            }
        else
            sudo su "$PG_USER" -c "psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $target_db -f $backup_file" || {
                log_error "恢复失败"
                exit 1
            }
        fi
    fi
    
    log_success "数据库恢复完成！"
}

# 主函数
main() {
    if [ $# -lt 1 ]; then
        show_usage
        exit 1
    fi
    
    local backup_file=$1
    shift
    
    # 检查 --list 选项
    if [[ "$*" == *"--list"* ]]; then
        check_backup_file "$backup_file"
        list_backup_content "$backup_file"
        exit 0
    fi
    
    # 获取目标数据库名
    local target_db=$1
    shift
    
    if [ -z "$target_db" ]; then
        # 尝试从备份文件名推断
        target_db=$(basename "$backup_file" | sed -E 's/_[0-9]{8}_[0-9]{6}\.dump.*$//' | sed -E 's/\.sql.*$//')
        if [ -z "$target_db" ]; then
            log_error "无法推断数据库名，请指定目标数据库"
            show_usage
            exit 1
        fi
        log_info "从文件名推断数据库名: $target_db"
    fi
    
    # 检查备份文件
    check_backup_file "$backup_file"
    
    # 确认恢复
    log_warning "即将恢复数据库 $target_db"
    log_warning "这将覆盖现有数据！"
    read -p "确认继续? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "恢复已取消"
        exit 0
    fi
    
    # 执行恢复
    restore_database "$backup_file" "$target_db" "$@"
}

# 运行主函数
main "$@"
