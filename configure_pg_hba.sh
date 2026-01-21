#!/bin/bash

# PostgreSQL pg_hba.conf 配置脚本
# 用于配置客户端访问权限

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
PG_VERSION="${PG_VERSION:-16}"
PG_HBA_FILE="/opt/local/etc/postgresql${PG_VERSION}/pg_hba.conf"
PG_CONF_FILE="/opt/local/etc/postgresql${PG_VERSION}/postgresql.conf"

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

# 检查文件是否存在
check_pg_hba_file() {
    if [ ! -f "$PG_HBA_FILE" ]; then
        log_error "pg_hba.conf 文件未找到: $PG_HBA_FILE"
        log_info "尝试查找其他可能的位置..."
        
        # 尝试其他可能的位置
        local possible_locations=(
            "/opt/local/var/db/postgresql${PG_VERSION}/defaultdb/pg_hba.conf"
            "/usr/local/var/postgresql${PG_VERSION}/pg_hba.conf"
            "/usr/local/etc/postgresql${PG_VERSION}/pg_hba.conf"
        )
        
        for loc in "${possible_locations[@]}"; do
            if [ -f "$loc" ]; then
                log_info "找到文件: $loc"
                PG_HBA_FILE="$loc"
                return 0
            fi
        done
        
        log_error "无法找到 pg_hba.conf 文件"
        log_info "请手动指定文件路径，或确保 PostgreSQL 已正确安装"
        exit 1
    fi
    
    log_success "找到 pg_hba.conf: $PG_HBA_FILE"
}

# 备份配置文件
backup_config() {
    local backup_file="${PG_HBA_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    log_info "备份配置文件到: $backup_file"
    sudo cp "$PG_HBA_FILE" "$backup_file"
    sudo chmod 600 "$backup_file"
    log_success "备份完成"
}

# 添加访问规则
add_access_rule() {
    local connection_type=$1  # local, host, hostssl, hostnossl
    local database=$2
    local user=$3
    local address=$4  # 可以是 IP、CIDR、或 "all"
    local auth_method=$5  # trust, md5, scram-sha-256, password
    
    log_info "添加访问规则..."
    log_info "  类型: $connection_type"
    log_info "  数据库: $database"
    log_info "  用户: $user"
    log_info "  地址: $address"
    log_info "  认证方法: $auth_method"
    
    # 构建规则行
    local rule_line
    if [ "$connection_type" = "local" ]; then
        rule_line="local    $database    $user    $auth_method"
    else
        rule_line="$connection_type    $database    $user    $address    $auth_method"
    fi
    
    # 检查规则是否已存在
    if sudo grep -q "^${rule_line}$" "$PG_HBA_FILE" 2>/dev/null; then
        log_warning "规则已存在，跳过添加"
        return 0
    fi
    
    # 添加规则（在文件末尾，但在注释之前）
    log_info "添加规则到配置文件..."
    
    # 如果文件末尾有注释，在注释之前插入
    if sudo grep -q "^# IPv6 local connections:" "$PG_HBA_FILE"; then
        # 在 IPv6 部分之前插入
        sudo sed -i.bak "/^# IPv6 local connections:/i\\
$rule_line
" "$PG_HBA_FILE"
    else
        # 直接追加到文件末尾
        echo "$rule_line" | sudo tee -a "$PG_HBA_FILE" > /dev/null
    fi
    
    log_success "规则已添加"
}

# 配置常见访问规则
configure_common_rules() {
    log_info "配置常见访问规则..."
    
    # 1. 本地连接（trust，用于本地管理）
    add_access_rule "local" "all" "all" "" "trust"
    
    # 2. IPv4 本地连接
    add_access_rule "host" "all" "all" "127.0.0.1/32" "trust"
    
    # 3. IPv6 本地连接
    add_access_rule "host" "all" "all" "::1/128" "trust"
    
    log_success "常见规则配置完成"
}

# 配置特定 IP 访问
configure_ip_access() {
    local ip_address=$1
    local database=${2:-"all"}
    local user=${3:-"all"}
    local auth_method=${4:-"md5"}
    
    log_info "配置 IP 访问: $ip_address"
    
    # 判断是单个 IP 还是 CIDR
    if [[ "$ip_address" == *"/"* ]]; then
        # CIDR 格式
        add_access_rule "host" "$database" "$user" "$ip_address" "$auth_method"
    else
        # 单个 IP，添加 /32
        add_access_rule "host" "$database" "$user" "${ip_address}/32" "$auth_method"
    fi
}

# 配置局域网访问
configure_lan_access() {
    local auth_method=${1:-"md5"}
    
    log_info "配置局域网访问（192.168.0.0/16）..."
    add_access_rule "host" "all" "all" "192.168.0.0/16" "$auth_method"
    log_success "局域网访问已配置"
}

# 配置 SSL 连接
configure_ssl() {
    log_info "检查 SSL 配置..."
    
    if [ ! -f "$PG_CONF_FILE" ]; then
        log_warning "postgresql.conf 未找到，跳过 SSL 配置"
        return 0
    fi
    
    # 检查 SSL 是否启用
    if sudo grep -q "^ssl = on" "$PG_CONF_FILE"; then
        log_info "SSL 已启用"
    else
        log_info "启用 SSL..."
        # 在文件末尾添加 SSL 配置
        echo "" | sudo tee -a "$PG_CONF_FILE" > /dev/null
        echo "# SSL Configuration" | sudo tee -a "$PG_CONF_FILE" > /dev/null
        echo "ssl = on" | sudo tee -a "$PG_CONF_FILE" > /dev/null
        log_success "SSL 已启用"
    fi
}

# 显示当前配置
show_config() {
    log_info "当前 pg_hba.conf 配置："
    echo ""
    sudo cat "$PG_HBA_FILE" | grep -v "^#" | grep -v "^$" || log_warning "没有活动规则"
    echo ""
}

# 重新加载配置
reload_config() {
    log_info "重新加载 PostgreSQL 配置..."
    
    # 尝试使用 pg_ctl 重新加载
    local pg_ctl="/opt/local/lib/postgresql${PG_VERSION}/bin/pg_ctl"
    local pg_data="/opt/local/var/db/postgresql${PG_VERSION}/defaultdb"
    
    if [ -f "$pg_ctl" ] && [ -d "$pg_data" ]; then
        sudo su _postgres -c "$pg_ctl -D $pg_data reload" 2>/dev/null && {
            log_success "配置已重新加载"
            return 0
        }
    fi
    
    # 尝试使用 port 重启服务
    log_info "尝试重启 PostgreSQL 服务..."
    sudo port unload postgresql${PG_VERSION}-server 2>/dev/null || true
    sleep 2
    sudo port load postgresql${PG_VERSION}-server 2>/dev/null && {
        log_success "PostgreSQL 服务已重启"
        return 0
    }
    
    log_warning "无法自动重新加载配置"
    log_info "请手动重启 PostgreSQL 服务："
    echo "  sudo port unload postgresql${PG_VERSION}-server"
    echo "  sudo port load postgresql${PG_VERSION}-server"
}

# 显示使用说明
show_usage() {
    echo "PostgreSQL pg_hba.conf 配置脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --ip <IP>              添加特定 IP 访问（例如: 192.168.2.102）"
    echo "  --ip-cidr <CIDR>       添加 CIDR 网段访问（例如: 192.168.0.0/16）"
    echo "  --lan                  配置局域网访问（192.168.0.0/16）"
    echo "  --user <user>          指定用户（默认: all）"
    echo "  --database <db>        指定数据库（默认: all）"
    echo "  --auth <method>        认证方法: trust, md5, scram-sha-256, password（默认: md5）"
    echo "  --ssl                  启用 SSL 连接"
    echo "  --no-ssl               允许非 SSL 连接（hostnossl）"
    echo "  --show                 显示当前配置"
    echo "  --common               配置常见规则（本地连接）"
    echo "  --file <path>          指定 pg_hba.conf 文件路径"
    echo ""
    echo "示例:"
    echo "  # 允许特定 IP 访问"
    echo "  $0 --ip 192.168.2.102 --user tony --database postgres"
    echo ""
    echo "  # 允许整个局域网访问"
    echo "  $0 --lan --auth md5"
    echo ""
    echo "  # 配置常见规则并允许局域网访问"
    echo "  $0 --common --lan"
    echo ""
    echo "  # 显示当前配置"
    echo "  $0 --show"
}

# 主函数
main() {
    local ip_address=""
    local ip_cidr=""
    local configure_lan=false
    local user="all"
    local database="all"
    local auth_method="md5"
    local use_ssl=false
    local no_ssl=false
    local show_only=false
    local configure_common=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --ip)
                ip_address="$2"
                shift 2
                ;;
            --ip-cidr)
                ip_cidr="$2"
                shift 2
                ;;
            --lan)
                configure_lan=true
                shift
                ;;
            --user)
                user="$2"
                shift 2
                ;;
            --database)
                database="$2"
                shift 2
                ;;
            --auth)
                auth_method="$2"
                shift 2
                ;;
            --ssl)
                use_ssl=true
                shift
                ;;
            --no-ssl)
                no_ssl=true
                shift
                ;;
            --show)
                show_only=true
                shift
                ;;
            --common)
                configure_common=true
                shift
                ;;
            --file)
                PG_HBA_FILE="$2"
                shift 2
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
    
    # 检查文件
    check_pg_hba_file
    
    # 如果只是显示配置
    if [ "$show_only" = true ]; then
        show_config
        exit 0
    fi
    
    # 备份配置
    backup_config
    
    # 配置常见规则
    if [ "$configure_common" = true ]; then
        configure_common_rules
    fi
    
    # 配置特定 IP
    if [ -n "$ip_address" ]; then
        local conn_type="host"
        if [ "$use_ssl" = true ]; then
            conn_type="hostssl"
        elif [ "$no_ssl" = true ]; then
            conn_type="hostnossl"
        fi
        add_access_rule "$conn_type" "$database" "$user" "${ip_address}/32" "$auth_method"
    fi
    
    # 配置 CIDR
    if [ -n "$ip_cidr" ]; then
        local conn_type="host"
        if [ "$use_ssl" = true ]; then
            conn_type="hostssl"
        elif [ "$no_ssl" = true ]; then
            conn_type="hostnossl"
        fi
        add_access_rule "$conn_type" "$database" "$user" "$ip_cidr" "$auth_method"
    fi
    
    # 配置局域网
    if [ "$configure_lan" = true ]; then
        local conn_type="host"
        if [ "$no_ssl" = true ]; then
            conn_type="hostnossl"
        fi
        add_access_rule "$conn_type" "all" "all" "192.168.0.0/16" "$auth_method"
    fi
    
    # 配置 SSL（如果需要）
    if [ "$use_ssl" = true ]; then
        configure_ssl
    fi
    
    # 显示配置
    echo ""
    show_config
    
    # 重新加载配置
    echo ""
    read -p "是否重新加载 PostgreSQL 配置? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        reload_config
    else
        log_info "请手动重启 PostgreSQL 服务使配置生效"
    fi
    
    log_success "配置完成！"
}

# 运行主函数
main "$@"
