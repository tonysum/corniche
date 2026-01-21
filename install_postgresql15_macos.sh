#!/bin/bash

# PostgreSQL 15 安装脚本 (macOS 12.7)
# 使用 MacPorts (port) 安装 PostgreSQL 15

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查 MacPorts 是否安装
check_macports() {
    if ! command_exists port; then
        print_error "MacPorts 未安装！"
        echo ""
        print_info "请先安装 MacPorts："
        echo "  1. 访问: https://www.macports.org/install.php"
        echo "  2. 下载适合您系统的安装包（.pkg 文件）"
        echo "  3. 运行安装包进行安装"
        echo ""
        print_info "或者使用命令行安装（需要 Xcode Command Line Tools）："
        echo "  # 下载安装脚本"
        echo "  cd /tmp"
        echo "  curl -O https://distfiles.macports.org/MacPorts/MacPorts-2.9.4.tar.bz2"
        echo "  tar xf MacPorts-2.9.4.tar.bz2"
        echo "  cd MacPorts-2.9.4"
        echo "  ./configure && make && sudo make install"
        echo ""
        read -p "是否已安装 MacPorts? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "需要先安装 MacPorts 才能继续"
            exit 1
        fi
        
        # 检查 port 命令是否可用
        if ! command_exists port; then
            print_error "MacPorts 未正确安装或未添加到 PATH"
            print_info "请将以下内容添加到 ~/.zprofile 或 ~/.zshrc："
            echo '  export PATH="/opt/local/bin:/opt/local/sbin:$PATH"'
            exit 1
        fi
    else
        print_success "MacPorts 已安装"
        # 确保 port 在 PATH 中
        export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
    fi
}

# 检查 PostgreSQL 是否已安装
check_existing_postgresql() {
    if command_exists psql; then
        local version=$(psql --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
        print_warning "检测到已安装的 PostgreSQL 版本: $version"
        read -p "是否继续安装 PostgreSQL 15? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "安装已取消"
            exit 0
        fi
    fi
}

# 安装 PostgreSQL 15
install_postgresql() {
    print_info "开始安装 PostgreSQL 15..."
    
    # 更新 MacPorts
    print_info "更新 MacPorts..."
    sudo port selfupdate
    
    # 检查 PostgreSQL 15 是否可用
    print_info "检查 PostgreSQL 15 是否可用..."
    if port search postgresql15-server | grep -q "postgresql15-server"; then
        print_info "找到 postgresql15-server 包"
    else
        print_warning "未找到 postgresql15-server 包，尝试搜索其他版本..."
        port search postgresql | grep -E "postgresql.*15" || print_warning "可能需要使用不同的包名"
    fi
    
    # 安装 PostgreSQL 15（需要 sudo 权限）
    print_info "安装 PostgreSQL 15 Server（需要管理员权限）..."
    print_warning "这可能需要一些时间，请耐心等待..."
    sudo port install postgresql15-server +universal
    
    print_success "PostgreSQL 15 安装完成！"
}

# 配置 PostgreSQL
configure_postgresql() {
    print_info "配置 PostgreSQL..."
    
    # MacPorts 的 PostgreSQL 路径
    local pg_path="/opt/local/lib/postgresql15/bin"
    local pg_bin="/opt/local/bin"
    
    # 添加 MacPorts 和 PostgreSQL 到 PATH
    if ! grep -q "/opt/local/bin" ~/.zprofile 2>/dev/null; then
        print_info "添加 MacPorts 到 PATH..."
        echo 'export PATH="/opt/local/bin:/opt/local/sbin:$PATH"' >> ~/.zprofile
    fi
    
        if [ -d "$pg_path" ] && ! grep -q "$pg_path" ~/.zprofile 2>/dev/null; then
            print_info "添加 PostgreSQL 15 到 PATH..."
            echo "export PATH=\"$pg_path:\$PATH\"" >> ~/.zprofile
        fi
    
    # 加载环境变量
    export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
    if [ -d "$pg_path" ]; then
        export PATH="$pg_path:$PATH"
    fi
}

# 初始化数据库（如果需要）
init_database() {
    print_info "检查数据库是否需要初始化..."
    
    # MacPorts 的 PostgreSQL 数据目录
    local pg_data_dir="/opt/local/var/db/postgresql15/defaultdb"
    local pg_bin="/opt/local/lib/postgresql15/bin"
    
    # 确保路径在 PATH 中
    export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
    if [ -d "$pg_bin" ]; then
        export PATH="$pg_bin:$PATH"
    fi
    
    # 检查 initdb 是否存在
    if [ ! -f "$pg_bin/initdb" ]; then
            print_error "initdb 命令未找到: $pg_bin/initdb"
            print_info "请确保 PostgreSQL 15 Server 已正确安装"
            print_info "尝试运行: sudo port install postgresql15-server"
        exit 1
    fi
    
    # 检查数据目录是否存在且非空
    if [ ! -d "$pg_data_dir" ] || [ -z "$(ls -A $pg_data_dir 2>/dev/null)" ]; then
        print_info "初始化数据库..."
        
        # 确保数据目录的父目录存在
        local pg_data_parent=$(dirname "$pg_data_dir")
        if [ ! -d "$pg_data_parent" ]; then
            print_info "创建数据目录的父目录: $pg_data_parent"
            sudo mkdir -p "$pg_data_parent"
            sudo chown root:wheel "$pg_data_parent"
            sudo chmod 755 "$pg_data_parent"
        fi
        
        # 检查 _postgres 用户是否存在
        if ! id "_postgres" &>/dev/null; then
            print_warning "_postgres 用户不存在，尝试创建..."
            # 创建 _postgres 用户（macOS 系统用户）
            sudo dscl . -create /Users/_postgres
            sudo dscl . -create /Users/_postgres UserShell /usr/bin/false
            sudo dscl . -create /Users/_postgres UniqueID 401
            sudo dscl . -create /Users/_postgres PrimaryGroupID 401
            sudo dscl . -create /Users/_postgres NFSHomeDirectory /var/empty
            sudo dscl . -create /Users/_postgres RealName "PostgreSQL Server"
            print_info "_postgres 用户已创建"
        fi
        
        # 如果目录存在但为空，先删除
        if [ -d "$pg_data_dir" ] && [ -z "$(ls -A $pg_data_dir 2>/dev/null)" ]; then
            print_info "清理空的数据目录..."
            sudo rmdir "$pg_data_dir" 2>/dev/null || true
        fi
        
        # 方法1: 使用 _postgres 用户初始化
        print_info "尝试使用 _postgres 用户初始化数据库..."
        if sudo su _postgres -c "$pg_bin/initdb -D $pg_data_dir" 2>&1; then
            print_success "数据库初始化完成"
            
            # 设置正确的权限
            print_info "设置数据目录权限..."
            sudo chown -R _postgres:_postgres "$pg_data_dir"
            sudo chmod 700 "$pg_data_dir"
        else
            print_warning "方法1失败，尝试方法2..."
            
            # 方法2: 先创建目录，再初始化
            print_info "创建数据目录并设置权限..."
            sudo mkdir -p "$pg_data_dir"
            sudo chown -R _postgres:_postgres "$pg_data_dir"
            sudo chmod 700 "$pg_data_dir"
            
            print_info "再次尝试初始化..."
            if sudo su _postgres -c "$pg_bin/initdb -D $pg_data_dir" 2>&1; then
                print_success "数据库初始化完成"
            else
                print_error "数据库初始化失败"
                echo ""
                print_info "请尝试手动初始化："
                echo "  1. 确保 _postgres 用户存在:"
                echo "     id _postgres"
                echo ""
                echo "  2. 创建数据目录:"
                echo "     sudo mkdir -p $pg_data_dir"
                echo "     sudo chown -R _postgres:_postgres $pg_data_dir"
                echo "     sudo chmod 700 $pg_data_dir"
                echo ""
                echo "  3. 初始化数据库:"
                echo "     sudo su _postgres -c '$pg_bin/initdb -D $pg_data_dir'"
                echo ""
                print_info "或者使用 MacPorts 的初始化脚本（如果存在）:"
                echo "  sudo port load postgresql16-server"
                echo ""
                read -p "是否继续安装? (y/n): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    exit 1
                fi
            fi
        fi
    else
        print_info "数据库已存在，跳过初始化"
        
        # 确保权限正确
        print_info "检查数据目录权限..."
        sudo chown -R _postgres:_postgres "$pg_data_dir" 2>/dev/null || true
        sudo chmod 700 "$pg_data_dir" 2>/dev/null || true
    fi
}

# 启动 PostgreSQL 服务
start_postgresql() {
    print_info "启动 PostgreSQL 服务..."
    
    # 确保路径在 PATH 中
    export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
    
    # 使用 port load 启动服务（需要 sudo）
    print_info "使用 MacPorts 启动 PostgreSQL 15 服务..."
    sudo port load postgresql15-server 2>/dev/null || {
        print_warning "port load 失败，尝试其他方式启动..."
        # 尝试使用 launchctl
        if [ -f "/opt/local/Library/LaunchDaemons/org.macports.postgresql15-server.plist" ]; then
            sudo launchctl load -w /opt/local/Library/LaunchDaemons/org.macports.postgresql15-server.plist
        else
            print_info "请手动启动服务，运行: sudo port load postgresql15-server"
        fi
    }
    
    # 等待服务启动
    sleep 3
    
    # 检查服务状态
    if sudo port installed postgresql15-server | grep -q "active"; then
        print_success "PostgreSQL 服务已启动"
    else
        print_warning "PostgreSQL 服务可能未正常启动"
        print_info "可以运行以下命令检查状态:"
        echo "  sudo port load postgresql15-server"
        echo "  或: sudo port unload postgresql15-server && sudo port load postgresql15-server"
    fi
}

# 创建数据库和用户（可选）
create_database_and_user() {
    print_info "是否创建数据库和用户？"
    read -p "创建数据库和用户? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "数据库名 (默认: crypto_data): " db_name
        db_name=${db_name:-crypto_data}
        
        read -p "用户名 (默认: crypto_user): " db_user
        db_user=${db_user:-crypto_user}
        
        read -sp "密码: " db_password
        echo
        
        # 确保路径在 PATH 中
        export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
        local pg_bin="/opt/local/lib/postgresql15/bin"
        if [ -d "$pg_bin" ]; then
            export PATH="$pg_bin:$PATH"
        fi
        
        # 创建用户（使用 _postgres 用户）
        print_info "创建用户: $db_user"
        if sudo su _postgres -c "psql -d postgres -c \"CREATE USER $db_user WITH PASSWORD '$db_password';\"" 2>/dev/null; then
            print_success "用户创建成功"
        else
            print_warning "用户可能已存在或创建失败"
        fi
        
        # 创建数据库
        print_info "创建数据库: $db_name"
        if sudo su _postgres -c "psql -d postgres -c \"CREATE DATABASE $db_name OWNER $db_user;\"" 2>/dev/null; then
            print_success "数据库创建成功"
        else
            print_warning "数据库可能已存在或创建失败"
        fi
        
        # 授予权限
        print_info "授予权限..."
        if sudo su _postgres -c "psql -d postgres -c \"GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;\"" 2>/dev/null; then
            print_success "权限授予成功"
        else
            print_warning "权限授予可能需要手动执行"
        fi
        
        print_success "数据库和用户创建完成！"
        echo ""
        print_info "连接信息："
        echo "  主机: localhost"
        echo "  端口: 5432"
        echo "  数据库: $db_name"
        echo "  用户: $db_user"
        echo "  密码: (您刚才输入的密码)"
    fi
}

# 显示使用说明
show_usage_info() {
    echo ""
    print_success "PostgreSQL 15 安装完成！"
    echo ""
    print_info "常用命令："
    echo "  启动服务:  sudo port load postgresql15-server"
    echo "  停止服务:  sudo port unload postgresql15-server"
    echo "  重启服务:  sudo port unload postgresql15-server && sudo port load postgresql15-server"
    echo "  查看状态:  sudo port installed postgresql15-server"
    echo "  查看运行状态:  ps aux | grep postgres"
    echo ""
    print_info "连接数据库："
    echo "  sudo su _postgres -c 'psql -d postgres'"
    echo "  或指定数据库: psql -U crypto_user -d crypto_data"
    echo "  注意: macOS 上 PostgreSQL 默认用户是 _postgres（带下划线）"
    echo ""
    print_info "配置文件位置："
    echo "  /opt/local/etc/postgresql15/postgresql.conf"
    echo "  /opt/local/var/db/postgresql15/defaultdb/postgresql.conf"
    echo ""
    print_info "数据目录："
    echo "  /opt/local/var/db/postgresql15/defaultdb"
    echo ""
    print_info "可执行文件位置："
    echo "  /opt/local/lib/postgresql15/bin/"
    echo ""
    print_warning "注意：MacPorts 安装的 PostgreSQL 通常在 /opt/local 目录下"
    print_warning "需要管理员权限 (sudo) 来启动/停止服务"
    echo ""
    print_info "如果命令找不到，请运行以下命令加载环境变量："
    echo "  export PATH=\"/opt/local/bin:/opt/local/sbin:\$PATH\""
    echo "  source ~/.zprofile"
    echo "  或重新打开终端"
}

# 主函数
main() {
    echo "=========================================="
    echo "  PostgreSQL 15 安装脚本 (macOS 12.7)"
    echo "=========================================="
    echo ""
    
    # 检查是否为 macOS
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_error "此脚本仅适用于 macOS"
        exit 1
    fi
    
    # 检查 MacPorts
    check_macports
    
    # 检查现有 PostgreSQL
    check_existing_postgresql
    
    # 安装 PostgreSQL
    install_postgresql
    
    # 配置 PostgreSQL
    configure_postgresql
    
    # 初始化数据库
    init_database
    
    # 启动服务
    start_postgresql
    
    # 创建数据库和用户（可选）
    create_database_and_user
    
    # 显示使用说明
    show_usage_info
}

# 运行主函数
main
