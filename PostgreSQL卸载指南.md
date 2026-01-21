# PostgreSQL 完全卸载指南

## 警告

⚠️ **此操作将永久删除所有 PostgreSQL 数据、配置和文件，且不可恢复！**

在执行卸载前，请确保：
1. ✅ 已备份所有重要数据
2. ✅ 已导出需要保留的数据库
3. ✅ 已记录配置文件中的重要设置
4. ✅ 确认不再需要 PostgreSQL

## 快速卸载（使用脚本）

### 方法1：交互式卸载（推荐）

```bash
./uninstall_postgresql.sh
```

脚本会：
- 询问确认
- 停止服务
- 卸载 MacPorts 包
- 删除数据、配置、日志
- 清理环境变量
- 可选删除用户和备份

### 方法2：指定版本卸载

```bash
./uninstall_postgresql.sh --version 16
```

### 方法3：非交互式卸载（危险）

```bash
./uninstall_postgresql.sh --skip-confirm
```

## 手动卸载步骤

如果不想使用脚本，可以按照以下步骤手动卸载：

### 步骤1：停止 PostgreSQL 服务

```bash
# 使用 MacPorts 停止
sudo port unload postgresql16-server

# 或使用 launchctl
sudo launchctl unload /opt/local/Library/LaunchDaemons/org.macports.postgresql16-server.plist

# 或直接 kill 进程
sudo pkill -9 postgres
```

### 步骤2：卸载 MacPorts 包

```bash
# 卸载服务器包（会自动卸载客户端包）
sudo port uninstall postgresql16-server

# 如果客户端包单独存在，也卸载
sudo port uninstall postgresql16

# 清理依赖
sudo port clean --all postgresql16-server
```

### 步骤3：删除数据目录

```bash
# MacPorts 数据目录
sudo rm -rf /opt/local/var/db/postgresql16
sudo rm -rf /opt/local/var/db/postgresql

# 其他可能的位置
sudo rm -rf /usr/local/var/postgresql16
sudo rm -rf /usr/local/var/postgresql
sudo rm -rf ~/PostgreSQL
```

### 步骤4：删除配置文件

```bash
# MacPorts 配置目录
sudo rm -rf /opt/local/etc/postgresql16
sudo rm -rf /opt/local/etc/postgresql

# 其他可能的位置
sudo rm -rf /usr/local/etc/postgresql16
sudo rm -rf /usr/local/etc/postgresql

# 用户配置文件
rm -f ~/.pgpass
rm -f ~/.psqlrc
```

### 步骤5：删除日志文件

```bash
sudo rm -rf /opt/local/var/log/postgresql16
sudo rm -rf /opt/local/var/log/postgresql
sudo rm -rf /usr/local/var/log/postgresql16
sudo rm -rf /usr/local/var/log/postgresql
```

### 步骤6：删除可执行文件（如果残留）

```bash
sudo rm -rf /opt/local/lib/postgresql16
sudo rm -rf /opt/local/lib/postgresql
sudo rm -rf /usr/local/lib/postgresql16
sudo rm -rf /usr/local/lib/postgresql
```

### 步骤7：删除 _postgres 用户（可选）

```bash
# 检查用户是否存在
id _postgres

# 删除用户
sudo dscl . -delete /Users/_postgres
```

### 步骤8：清理环境变量

编辑以下文件，删除 PostgreSQL 相关的环境变量：

```bash
# 编辑配置文件
nano ~/.zprofile
# 或
nano ~/.zshrc
# 或
nano ~/.bash_profile

# 删除类似以下的行：
# export PATH="/opt/local/lib/postgresql16/bin:$PATH"
# export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
```

### 步骤9：删除备份文件（可选）

```bash
# 如果不再需要备份
sudo rm -rf /backup/postgresql
rm -rf ~/backup/postgresql
```

## 验证卸载

### 检查进程

```bash
ps aux | grep postgres
# 应该没有输出
```

### 检查命令

```bash
which psql
# 应该返回：psql not found
```

### 检查包

```bash
port installed | grep postgresql
# 应该没有输出
```

### 检查目录

```bash
ls -la /opt/local/var/db/ | grep postgresql
ls -la /opt/local/etc/ | grep postgresql
# 应该没有输出
```

## 卸载后清理

### 1. 重新加载环境

```bash
# 重新加载 shell 配置
source ~/.zprofile
# 或重新打开终端
```

### 2. 清理 MacPorts（可选）

```bash
# 清理未使用的依赖
sudo port uninstall inactive

# 清理构建文件
sudo port clean --all installed
```

### 3. 清理系统缓存（可选）

```bash
# macOS 系统缓存
sudo rm -rf /Library/Caches/com.apple.*
```

## 常见问题

### Q1: 卸载后如何重新安装？

A: 使用安装脚本重新安装：
```bash
./install_postgresql16_macos.sh
```

### Q2: 卸载时提示权限被拒绝？

A: 确保使用 `sudo` 执行删除操作，或检查文件/目录的所有者。

### Q3: 卸载后 psql 命令仍可用？

A: 可能安装了多个 PostgreSQL 版本，或通过其他方式安装。检查：
```bash
which psql
port installed | grep postgresql
brew list | grep postgresql  # 如果使用 Homebrew
```

### Q4: 如何只卸载服务器，保留客户端？

A: 只卸载服务器包：
```bash
sudo port uninstall postgresql16-server
# 客户端工具会保留
```

### Q5: 卸载后数据可以恢复吗？

A: **不可以**。一旦删除数据目录，数据就无法恢复（除非有备份）。请确保在卸载前备份重要数据。

### Q6: 如何备份数据后再卸载？

A: 使用备份脚本：
```bash
# 备份所有数据库
./pg_backup.sh daily

# 或手动备份
pg_dumpall > backup.sql

# 然后卸载
./uninstall_postgresql.sh
```

## 卸载检查清单

卸载前检查：

- [ ] 已备份所有数据库
- [ ] 已导出配置文件（如果需要）
- [ ] 已记录数据库连接信息
- [ ] 已停止所有使用 PostgreSQL 的应用
- [ ] 已确认不再需要 PostgreSQL

卸载后检查：

- [ ] PostgreSQL 服务已停止
- [ ] MacPorts 包已卸载
- [ ] 数据目录已删除
- [ ] 配置文件已删除
- [ ] 环境变量已清理
- [ ] psql 命令不可用
- [ ] 没有残留进程

## 安全提示

1. **备份优先**：卸载前务必备份数据
2. **测试环境**：先在测试环境验证卸载流程
3. **逐步执行**：如果不确定，逐步执行并验证
4. **保留备份**：即使卸载后，也保留备份文件一段时间

## 参考资源

- [MacPorts 卸载文档](https://guide.macports.org/#installing.uninstalling)
- [PostgreSQL 卸载文档](https://www.postgresql.org/docs/current/installation.html)
