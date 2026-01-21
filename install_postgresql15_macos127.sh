#!/bin/bash

# PostgreSQL 安装脚本 for macOS 12.7
# 适用于 Intel 和 Apple Silicon (ARM) 芯片

set -e  # 遇到错误时退出脚本

echo "=== PostgreSQL 安装脚本 for macOS 12.7 ==="
echo "检测系统信息..."

# 检测 macOS 版本
macos_version=$(sw_vers -productVersion)
echo "当前 macOS 版本: $macos_version"

if [[ "$macos_version" != 12.7* ]]; then
    echo "警告: 本脚本专为 macOS 12.7 设计，当前版本是 $macos_version"
    echo "可能需要进行调整才能正常工作"
    read -p "是否继续？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检测芯片架构
architecture=$(uname -m)
echo "系统架构: $architecture"

if [[ "$architecture" == "arm64" ]]; then
    echo "检测到 Apple Silicon (ARM) 芯片"
    BREW_PREFIX="/opt/homebrew"
    PG_BREW_NAME="postgresql@16"  # 使用较新版本以获得更好的 ARM 支持
else
    echo "检测到 Intel 芯片"
    BREW_PREFIX="/usr/local"
    PG_BREW_NAME="postgresql@15"
fi

# 检查是否已安装 Homebrew
echo -e "\n=== 检查 Homebrew 安装 ==="
if ! command -v brew &> /dev/null; then
    echo "未找到 Homebrew，正在安装..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # 设置 Homebrew 环境变量
    if [[ "$architecture" == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zshrc
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    echo "Homebrew 已安装"
    brew update
fi

# 安装 PostgreSQL
echo -e "\n=== 安装 PostgreSQL ==="
echo "将安装: $PG_BREW_NAME"

# 检查是否已安装 PostgreSQL
if brew list $PG_BREW_NAME &> /dev/null; then
    echo "$PG_BREW_NAME 已安装，跳过安装步骤"
else
    echo "正在安装 $PG_BREW_NAME..."
    brew install $PG_BREW_NAME
fi

# 配置 PostgreSQL 服务
echo -e "\n=== 配置 PostgreSQL 服务 ==="

# 创建数据目录（如果需要）
PG_DATA="$BREW_PREFIX/var/postgresql"
echo "PostgreSQL 数据目录: $PG_DATA"

# 初始化数据库（如果是第一次安装）
if [ ! -d "$PG_DATA" ] || [ -z "$(ls -A $PG_DATA 2>/dev/null)" ]; then
    echo "初始化数据库..."
    initdb "$PG_DATA" --encoding=utf8 --auth=trust
else
    echo "数据库已初始化"
fi

# 配置启动服务
echo -e "\n=== 配置启动服务 ==="

# 停止可能运行的服务
brew services stop $PG_BREW_NAME 2>/dev/null || true

# 启动 PostgreSQL 服务
echo "启动 PostgreSQL 服务..."
brew services start $PG_BREW_NAME

# 等待服务启动
echo -n "等待 PostgreSQL 启动"
for i in {1..30}; do
    if brew services list | grep $PG_BREW_NAME | grep -q "started"; then
        echo -e "\nPostgreSQL 服务已启动"
        break
    fi
    echo -n "."
    sleep 1
done

# 检查服务状态
echo -e "\n=== 服务状态 ==="
brew services list | grep $PG_BREW_NAME

# 创建默认数据库和用户
echo -e "\n=== 创建默认数据库和用户 ==="

# 设置 PATH 以便访问 PostgreSQL 工具
export PATH="$BREW_PREFIX/opt/$PG_BREW_NAME/bin:$PATH"

# 检查是否已存在 postgres 用户
if psql postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='postgres'" | grep -q 1; then
    echo "postgres 用户已存在"
else
    echo "创建 postgres 用户..."
    # 注意：在实际生产环境中，应该设置密码
    createuser -s postgres
fi

# 创建开发数据库
echo "创建开发数据库..."
createdb mydatabase 2>/dev/null || echo "数据库 'mydatabase' 已存在或创建失败"

# 测试连接
echo -e "\n=== 测试数据库连接 ==="
if psql -lqt 2>/dev/null; then
    echo "PostgreSQL 连接测试成功！"
    echo -e "\n可用数据库:"
    psql -lqt | head -10
else
    echo "警告: 无法连接到 PostgreSQL"
fi

# 显示安装信息
echo -e "\n=== 安装完成 ==="
echo "PostgreSQL 已成功安装！"
echo ""
echo "重要信息:"
echo "1. PostgreSQL 版本: $PG_BREW_NAME"
echo "2. 数据目录: $PG_DATA"
echo "3. 配置文件: $BREW_PREFIX/etc/$PG_BREW_NAME/postgresql.conf"
echo ""
echo "管理命令:"
echo "  启动服务: brew services start $PG_BREW_NAME"
echo "  停止服务: brew services stop $PG_BREW_NAME"
echo "  重启服务: brew services restart $PG_BREW_NAME"
echo "  查看状态: brew services list"
echo ""
echo "连接数据库:"
echo "  psql postgres"
echo "  psql mydatabase"
echo ""
echo "安全建议:"
echo "  1. 运行以下命令为 postgres 用户设置密码:"
echo "     psql -c \"ALTER USER postgres WITH PASSWORD '你的密码';\""
echo "  2. 修改 pg_hba.conf 文件以配置认证方式"
echo "    位置: $BREW_PREFIX/etc/$PG_BREW_NAME/pg_hba.conf"
echo ""
echo "故障排除:"
echo "  查看日志: tail -f $BREW_PREFIX/var/log/$PG_BREW_NAME.log"

# 显示配置文件位置
echo -e "\n配置文件位置:"
ls -la $BREW_PREFIX/etc/$PG_BREW_NAME/ 2>/dev/null || echo "配置文件目录不存在，可能需要手动创建"

exit 0