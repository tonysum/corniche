#!/bin/bash

# PostgreSQL 安装检测脚本

echo "=== PostgreSQL 安装检测 ==="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

POSTGRESQL_INSTALLED=false

# 1. 检查 psql 命令是否存在
echo -e "${BLUE}1. 检查 psql 命令...${NC}"
if command -v psql &> /dev/null; then
    PSQL_VERSION=$(psql --version 2>/dev/null | head -1)
    echo -e "${GREEN}✓ psql 已安装${NC}"
    echo "  版本: $PSQL_VERSION"
    PSQL_PATH=$(which psql)
    echo "  路径: $PSQL_PATH"
    POSTGRESQL_INSTALLED=true
else
    echo -e "${RED}✗ psql 未找到${NC}"
fi
echo ""

# 2. 检查 PostgreSQL 服务
echo -e "${BLUE}2. 检查 PostgreSQL 服务状态...${NC}"

# 尝试 systemd
if systemctl list-unit-files | grep -q postgresql; then
    echo "检测到 systemd 服务："
    systemctl list-unit-files | grep postgresql | while read line; do
        SERVICE_NAME=$(echo $line | awk '{print $1}')
        STATUS=$(systemctl is-active $SERVICE_NAME 2>/dev/null || echo "unknown")
        ENABLED=$(systemctl is-enabled $SERVICE_NAME 2>/dev/null || echo "unknown")
        
        if [ "$STATUS" = "active" ]; then
            echo -e "  ${GREEN}✓ $SERVICE_NAME: 运行中 (enabled: $ENABLED)${NC}"
            POSTGRESQL_INSTALLED=true
        elif [ "$STATUS" = "inactive" ]; then
            echo -e "  ${YELLOW}○ $SERVICE_NAME: 已停止 (enabled: $ENABLED)${NC}"
            POSTGRESQL_INSTALLED=true
        else
            echo -e "  ${YELLOW}? $SERVICE_NAME: 状态未知${NC}"
            POSTGRESQL_INSTALLED=true
        fi
    done
elif service postgresql status &> /dev/null; then
    echo "检测到 service 命令："
    service postgresql status | head -5
    POSTGRESQL_INSTALLED=true
else
    echo -e "${YELLOW}⚠ 未找到 systemd 或 service 管理的 PostgreSQL 服务${NC}"
fi
echo ""

# 3. 检查 PostgreSQL 进程
echo -e "${BLUE}3. 检查 PostgreSQL 进程...${NC}"
PG_PROCESSES=$(ps aux | grep -E "[p]ostgres|[p]ostmaster" | grep -v "grep")
if [ ! -z "$PG_PROCESSES" ]; then
    # 进一步过滤，确保是真正的 PostgreSQL 进程
    REAL_PG=$(echo "$PG_PROCESSES" | grep -E "/usr/bin/postgres|/usr/local/bin/postgres|/opt.*/bin/postgres|postmaster.*postgres" | grep -v "grep")
    if [ ! -z "$REAL_PG" ]; then
        echo -e "${GREEN}✓ 发现 PostgreSQL 进程：${NC}"
        echo "$REAL_PG" | head -3
        POSTGRESQL_INSTALLED=true
    else
        echo -e "${YELLOW}○ 未发现运行中的 PostgreSQL 进程${NC}"
    fi
else
    echo -e "${YELLOW}○ 未发现运行中的 PostgreSQL 进程${NC}"
fi
echo ""

# 4. 检查 PostgreSQL 数据目录
echo -e "${BLUE}4. 检查 PostgreSQL 数据目录...${NC}"
COMMON_DATA_DIRS=(
    "/var/lib/postgresql"
    "/usr/local/var/postgres"
    "/opt/homebrew/var/postgres"
    "/Library/PostgreSQL"
    "/var/lib/pgsql"
    "/opt/postgresql"
)

FOUND_DIR=false
for DIR in "${COMMON_DATA_DIRS[@]}"; do
    if [ -d "$DIR" ]; then
        echo -e "${GREEN}✓ 找到数据目录: $DIR${NC}"
        ls -ld "$DIR" 2>/dev/null | awk '{print "  权限: " $1 " 所有者: " $3 ":" $4}'
        FOUND_DIR=true
        POSTGRESQL_INSTALLED=true
    fi
done

if [ "$FOUND_DIR" = false ]; then
    echo -e "${YELLOW}○ 未找到常见的数据目录${NC}"
fi
echo ""

# 5. 检查 PostgreSQL 配置文件
echo -e "${BLUE}5. 检查 PostgreSQL 配置文件...${NC}"
COMMON_CONFIG_FILES=(
    "/etc/postgresql"
    "/usr/local/etc/postgresql"
    "/opt/homebrew/etc/postgresql"
    "/Library/PostgreSQL/*/data/postgresql.conf"
    "/var/lib/pgsql/data/postgresql.conf"
)

FOUND_CONFIG=false
for CONFIG in "${COMMON_CONFIG_FILES[@]}"; do
    if ls $CONFIG &> /dev/null 2>&1; then
        echo -e "${GREEN}✓ 找到配置文件: $CONFIG${NC}"
        FOUND_CONFIG=true
        POSTGRESQL_INSTALLED=true
    fi
done

if [ "$FOUND_CONFIG" = false ]; then
    echo -e "${YELLOW}○ 未找到配置文件${NC}"
fi
echo ""

# 6. 检查 PostgreSQL 端口监听
echo -e "${BLUE}6. 检查 PostgreSQL 端口监听 (5432)...${NC}"
if command -v netstat &> /dev/null; then
    PORT_CHECK=$(netstat -tuln 2>/dev/null | grep :5432)
elif command -v ss &> /dev/null; then
    PORT_CHECK=$(ss -tuln 2>/dev/null | grep :5432)
elif command -v lsof &> /dev/null; then
    PORT_CHECK=$(lsof -i :5432 2>/dev/null)
else
    PORT_CHECK=""
fi

if [ ! -z "$PORT_CHECK" ]; then
    echo -e "${GREEN}✓ PostgreSQL 正在监听端口 5432${NC}"
    echo "$PORT_CHECK" | head -2
    POSTGRESQL_INSTALLED=true
else
    echo -e "${YELLOW}○ 端口 5432 未被监听（服务可能未启动）${NC}"
fi
echo ""

# 7. 检查包管理器中的 PostgreSQL
echo -e "${BLUE}7. 检查包管理器安装记录...${NC}"

# macOS Homebrew
if command -v brew &> /dev/null; then
    BREW_PG=$(brew list | grep postgresql 2>/dev/null)
    if [ ! -z "$BREW_PG" ]; then
        echo -e "${GREEN}✓ Homebrew 已安装 PostgreSQL 相关包：${NC}"
        echo "$BREW_PG" | head -5
        POSTGRESQL_INSTALLED=true
    fi
fi

# Ubuntu/Debian apt
if command -v dpkg &> /dev/null; then
    DPKG_PG=$(dpkg -l | grep postgresql 2>/dev/null)
    if [ ! -z "$DPKG_PG" ]; then
        echo -e "${GREEN}✓ apt 已安装 PostgreSQL 相关包：${NC}"
        echo "$DPKG_PG" | head -5
        POSTGRESQL_INSTALLED=true
    fi
fi

# CentOS/RHEL yum/rpm
if command -v rpm &> /dev/null; then
    RPM_PG=$(rpm -qa | grep postgresql 2>/dev/null)
    if [ ! -z "$RPM_PG" ]; then
        echo -e "${GREEN}✓ rpm 已安装 PostgreSQL 相关包：${NC}"
        echo "$RPM_PG" | head -5
        POSTGRESQL_INSTALLED=true
    fi
fi

if [ -z "$BREW_PG" ] && [ -z "$DPKG_PG" ] && [ -z "$RPM_PG" ]; then
    echo -e "${YELLOW}○ 未在包管理器中找到 PostgreSQL${NC}"
fi
echo ""

# 8. 尝试连接测试
if command -v psql &> /dev/null; then
    echo -e "${BLUE}8. 测试 PostgreSQL 连接...${NC}"
    
    # 尝试连接默认数据库
    if PGPASSWORD="" psql -U postgres -d postgres -c "SELECT version();" &> /dev/null 2>&1; then
        echo -e "${GREEN}✓ 可以连接到 PostgreSQL（用户: postgres）${NC}"
        psql -U postgres -d postgres -c "SELECT version();" 2>/dev/null | head -2
    elif PGPASSWORD="" psql -U $USER -d postgres -c "SELECT version();" &> /dev/null 2>&1; then
        echo -e "${GREEN}✓ 可以连接到 PostgreSQL（用户: $USER）${NC}"
        psql -U $USER -d postgres -c "SELECT version();" 2>/dev/null | head -2
    else
        echo -e "${YELLOW}○ 无法连接到 PostgreSQL（可能需要配置认证）${NC}"
    fi
    echo ""
fi

# 总结（需要至少两个指标确认）
INSTALLED_COUNT=0
[ "$(command -v psql &> /dev/null && echo 1 || echo 0)" = "1" ] && INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
[ ! -z "$BREW_PG$DPKG_PG$RPM_PG" ] && INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
[ "$FOUND_DIR" = true ] && INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
[ "$FOUND_CONFIG" = true ] && INSTALLED_COUNT=$((INSTALLED_COUNT + 1))

echo "=== 检测总结 ==="
if [ "$INSTALLED_COUNT" -ge 1 ] || [ "$POSTGRESQL_INSTALLED" = true ]; then
    echo -e "${GREEN}✓ PostgreSQL 已安装${NC}"
    echo ""
    echo "下一步操作："
    echo "  1. 启动服务: sudo systemctl start postgresql (Linux)"
    echo "    或: brew services start postgresql@15 (macOS)"
    echo "  2. 创建数据库: createdb mydb"
    echo "  3. 连接数据库: psql -d mydb"
else
    echo -e "${RED}✗ PostgreSQL 未安装或未检测到${NC}"
    echo ""
    echo "安装方法："
    echo "  macOS (Homebrew):"
    echo "    brew install postgresql@15"
    echo "    brew services start postgresql@15"
    echo ""
    echo "  Ubuntu/Debian:"
    echo "    sudo apt-get update"
    echo "    sudo apt-get install postgresql postgresql-contrib"
    echo "    sudo systemctl start postgresql"
    echo ""
    echo "  CentOS/RHEL:"
    echo "    sudo yum install postgresql-server postgresql-contrib"
    echo "    sudo postgresql-setup initdb"
    echo "    sudo systemctl start postgresql"
fi
echo ""
