# PostgreSQL 检测方法

## 快速检测命令

### 1. 检查 psql 命令（最简单）

```bash
# 检查 psql 是否存在
which psql
# 或
command -v psql

# 查看版本
psql --version
```

**结果判断**：
- 如果返回路径（如 `/usr/bin/psql`），说明已安装
- 如果返回空或 `command not found`，说明未安装

### 2. 检查 PostgreSQL 服务状态

#### Linux (systemd)
```bash
# 检查服务状态
systemctl status postgresql
# 或
systemctl status postgresql@15

# 列出所有 PostgreSQL 相关服务
systemctl list-unit-files | grep postgresql
```

#### macOS (Homebrew)
```bash
# 检查服务状态
brew services list | grep postgresql

# 检查是否运行
brew services info postgresql@15
```

#### 通用方法
```bash
# 检查进程
ps aux | grep postgres | grep -v grep

# 检查端口监听（默认 5432）
netstat -tuln | grep 5432
# 或
ss -tuln | grep 5432
# 或 (macOS)
lsof -i :5432
```

### 3. 检查安装包

#### macOS (Homebrew)
```bash
brew list | grep postgresql
```

#### Ubuntu/Debian
```bash
dpkg -l | grep postgresql
# 或
apt list --installed | grep postgresql
```

#### CentOS/RHEL
```bash
rpm -qa | grep postgresql
# 或
yum list installed | grep postgresql
```

### 4. 检查数据目录和配置文件

```bash
# 常见数据目录位置
ls -la /var/lib/postgresql        # Linux 常见位置
ls -la /usr/local/var/postgres    # macOS Homebrew
ls -la /opt/homebrew/var/postgres  # macOS Apple Silicon
ls -la /Library/PostgreSQL         # macOS 官方安装

# 常见配置文件位置
ls -la /etc/postgresql            # Linux
ls -la /usr/local/etc/postgresql  # macOS Homebrew
```

### 5. 尝试连接测试

```bash
# 尝试连接（会提示输入密码或显示错误）
psql -U postgres -d postgres -c "SELECT version();"

# 或使用当前用户
psql -d postgres -c "SELECT version();"

# 列出所有数据库
psql -l
```

## 一键检测脚本

使用项目中的检测脚本：

```bash
# 运行检测脚本
./check_postgresql.sh
```

脚本会检查：
1. ✅ psql 命令是否存在
2. ✅ 服务状态
3. ✅ 运行中的进程
4. ✅ 数据目录
5. ✅ 配置文件
6. ✅ 端口监听
7. ✅ 包管理器记录
8. ✅ 连接测试

## 检测结果判断

### 已安装的迹象（至少满足一项）：
- ✅ `psql --version` 返回版本信息
- ✅ `systemctl status postgresql` 显示服务信息
- ✅ `ps aux | grep postgres` 显示 postgres 进程
- ✅ 包管理器显示已安装 postgresql 包
- ✅ 存在 `/var/lib/postgresql` 或类似数据目录

### 未安装的迹象（全部满足）：
- ❌ `psql: command not found`
- ❌ 包管理器中没有 postgresql 包
- ❌ 没有 postgres 进程运行
- ❌ 端口 5432 未被监听

## 常见问题

### Q: psql 命令存在但无法连接？
**A**: 可能是服务未启动，尝试：
```bash
# Linux
sudo systemctl start postgresql

# macOS
brew services start postgresql@15
```

### Q: 如何确认 PostgreSQL 正在运行？
**A**: 检查端口和进程：
```bash
# 检查端口
lsof -i :5432

# 检查进程
ps aux | grep "[p]ostgres"
```

### Q: 检测到安装但服务未启动？
**A**: 启动服务：
```bash
# Linux
sudo systemctl enable postgresql
sudo systemctl start postgresql

# macOS
brew services start postgresql@15
```

## 安装 PostgreSQL（如果未安装）

### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
```

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### CentOS/RHEL
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## 验证安装

安装后验证：
```bash
# 1. 检查版本
psql --version

# 2. 检查服务状态
systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS

# 3. 测试连接
psql -U postgres -c "SELECT version();"
```
