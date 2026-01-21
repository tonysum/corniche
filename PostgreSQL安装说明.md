# PostgreSQL 16 安装指南 (macOS 12.7)

## 快速安装

运行安装脚本：

```bash
./install_postgresql16_macos.sh
```

## 脚本功能

1. ✅ 自动检查 MacPorts 是否安装
2. ✅ 使用 MacPorts (port) 安装 PostgreSQL 16
3. ✅ 自动初始化数据库
4. ✅ 启动 PostgreSQL 服务
5. ✅ 可选：创建数据库和用户（交互式）

## 系统要求

- macOS 12.7 或更高版本
- MacPorts 已安装（脚本会检查）
- 管理员权限（sudo，用于安装和启动服务）
- Xcode Command Line Tools（MacPorts 需要）

## 安装步骤

### 1. 安装 MacPorts（如果未安装）

如果还没有安装 MacPorts：

**方法1：使用安装包（推荐）**
1. 访问 https://www.macports.org/install.php
2. 下载适合您系统的 `.pkg` 安装包
3. 运行安装包进行安装

**方法2：使用命令行**
```bash
# 需要先安装 Xcode Command Line Tools
xcode-select --install

# 下载并安装 MacPorts
cd /tmp
curl -O https://distfiles.macports.org/MacPorts/MacPorts-2.9.4.tar.bz2
tar xf MacPorts-2.9.4.tar.bz2
cd MacPorts-2.9.4
./configure && make && sudo make install
```

**配置 PATH**
将以下内容添加到 `~/.zprofile` 或 `~/.zshrc`：
```bash
export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
```

然后运行：
```bash
source ~/.zprofile
```

### 2. 运行安装脚本

```bash
cd /Users/tony/Documents/crypto/corniche
./install_postgresql16_macos.sh
```

### 3. 按照提示操作

脚本会：
- 检查 MacPorts 是否安装
- 检查是否已有 PostgreSQL，如果有会提示确认
- 更新 MacPorts 软件包列表
- 安装 PostgreSQL 16（需要 sudo 权限）
- 初始化数据库
- 启动服务（需要 sudo 权限）
- 询问是否创建数据库和用户

### 3. 创建数据库和用户（推荐）

脚本会询问是否创建数据库和用户，建议创建：
- **数据库名**: `crypto_data`（或自定义）
- **用户名**: `crypto_user`（或自定义）
- **密码**: 输入一个安全的密码

## 安装后的配置

### 1. 加载环境变量

如果命令找不到，运行：

```bash
export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
source ~/.zprofile
```

或重新打开终端窗口。

### 2. 验证安装

```bash
# 检查版本
psql --version

# 检查安装状态
sudo port installed postgresql16-server

# 检查服务运行状态
ps aux | grep postgres

# 连接数据库
psql -U postgres -d postgres
```

## 常用命令

### 服务管理

```bash
# 启动服务（需要 sudo）
sudo port load postgresql16-server

# 停止服务（需要 sudo）
sudo port unload postgresql16-server

# 重启服务（需要 sudo）
sudo port unload postgresql16-server && sudo port load postgresql16-server

# 查看安装状态
sudo port installed postgresql16-server

# 查看运行状态
ps aux | grep postgres
```

### 数据库操作

```bash
# 连接到默认数据库（macOS 上 PostgreSQL 默认用户是 _postgres，带下划线）
sudo su _postgres -c 'psql -d postgres'

# 或者直接使用 psql（如果已配置信任认证）
psql -U _postgres -d postgres

# 连接到指定数据库
psql -U crypto_user -d crypto_data

# 列出所有数据库
sudo su _postgres -c 'psql -d postgres -c "\l"'

# 列出所有用户
sudo su _postgres -c 'psql -d postgres -c "\du"'
```

## 配置文件位置

- **配置文件**: `/opt/local/etc/postgresql16/postgresql.conf`
- **数据目录**: `/opt/local/var/db/postgresql16/defaultdb`
- **日志文件**: `/opt/local/var/log/postgresql16/`
- **可执行文件**: `/opt/local/lib/postgresql16/bin/`

> **注意**: MacPorts 安装的软件通常在 `/opt/local` 目录下

## 配置 .env 文件

安装完成后，在项目根目录的 `.env` 文件中配置：

```env
# PostgreSQL 数据库配置
PG_HOST=localhost
PG_PORT=5432
PG_DB=crypto_data
PG_USER=crypto_user
PG_PASSWORD=your_password
```

## 故障排除

### 1. 命令找不到

如果 `psql` 或 `port` 命令找不到：

```bash
# 添加 MacPorts 到 PATH
export PATH="/opt/local/bin:/opt/local/sbin:$PATH"

# 添加 PostgreSQL 到 PATH
export PATH="/opt/local/lib/postgresql16/bin:$PATH"

# 或永久添加到 ~/.zprofile
echo 'export PATH="/opt/local/bin:/opt/local/sbin:$PATH"' >> ~/.zprofile
echo 'export PATH="/opt/local/lib/postgresql16/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile
```

### 2. 服务无法启动

检查日志：

```bash
# MacPorts 的日志位置
tail -f /opt/local/var/log/postgresql16/postgresql.log

# 或检查系统日志
tail -f /var/log/system.log | grep postgres
```

尝试手动启动：

```bash
# 检查服务是否已加载
sudo port installed postgresql16-server

# 尝试加载服务
sudo port load postgresql16-server

# 如果失败，检查配置文件（使用 _postgres 用户）
sudo su _postgres -c '/opt/local/lib/postgresql16/bin/postgres -D /opt/local/var/db/postgresql16/defaultdb'
```

### 3. 端口被占用

检查端口占用：

```bash
lsof -i :5432
```

如果端口被占用，可以修改 PostgreSQL 端口或停止占用端口的进程。

### 4. 权限问题

如果遇到权限问题：

```bash
# 检查数据目录权限
ls -la /opt/local/var/db/postgresql16/defaultdb

# MacPorts 安装的 PostgreSQL 在 macOS 上以 _postgres 用户运行（带下划线）
# 如果需要，修改权限
sudo chown -R _postgres:_postgres /opt/local/var/db/postgresql16/defaultdb
sudo chmod 700 /opt/local/var/db/postgresql16/defaultdb
```

### 5. MacPorts 相关问题

如果遇到 MacPorts 相关错误：

```bash
# 更新 MacPorts
sudo port selfupdate

# 升级所有已安装的包
sudo port upgrade outdated

# 查看 PostgreSQL 16 的详细信息
port info postgresql16-server

# 查看依赖关系
port deps postgresql16-server
```

## 卸载 PostgreSQL

如果需要卸载：

```bash
# 停止服务
sudo port unload postgresql16-server

# 卸载 PostgreSQL（保留数据）
sudo port uninstall postgresql16-server

# 完全卸载（包括数据，谨慎操作）
sudo port uninstall postgresql16-server
sudo rm -rf /opt/local/var/db/postgresql16
```

## 参考资源

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/16/)
- [MacPorts 官网](https://www.macports.org/)
- [MacPorts PostgreSQL 16 Server 包信息](https://ports.macports.org/port/postgresql16-server/)
