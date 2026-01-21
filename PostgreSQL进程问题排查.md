# PostgreSQL 进程问题排查指南

## 问题：卸载后仍能看到 postgres 进程

### 可能的原因

1. **进程没有被正确终止**
   - 进程可能仍在运行
   - 可能是僵尸进程
   - 可能有多个 PostgreSQL 实例

2. **通过其他方式安装的 PostgreSQL**
   - Homebrew 安装的 PostgreSQL
   - 手动编译安装的 PostgreSQL
   - 其他包管理器安装的

3. **服务自动重启**
   - launchd 服务自动重启
   - systemd 服务（Linux）
   - 其他进程管理器

4. **残留的锁文件**
   - postmaster.pid 文件存在
   - 共享内存未清理

## 诊断步骤

### 步骤1：检查进程详情

```bash
# 使用检查脚本
./check_postgres_processes.sh --all

# 或手动检查
ps aux | grep postgres
ps -ef | grep postgres
```

### 步骤2：查看进程来源

```bash
# 检查进程的完整命令行
ps aux | grep postgres | grep -v grep

# 查看进程树
pstree -p $(pgrep postgres | head -1)

# 查看进程打开的文件
sudo lsof -p $(pgrep postgres | head -1)
```

### 步骤3：检查服务状态

```bash
# MacPorts
port installed | grep postgresql
sudo port unload postgresql16-server

# Homebrew
brew services list | grep postgresql
brew services stop postgresql

# launchd
launchctl list | grep postgresql
sudo launchctl list | grep postgresql
```

### 步骤4：检查锁文件

```bash
# 查找 postmaster.pid 文件
sudo find /opt/local /usr/local /tmp -name "postmaster.pid" 2>/dev/null

# 检查共享内存
ipcs -m | grep postgres
```

## 解决方案

### 方案1：使用检查脚本终止进程

```bash
# 检查并终止所有进程
./check_postgres_processes.sh --kill

# 清理残留
./check_postgres_processes.sh --cleanup
```

### 方案2：手动终止进程

```bash
# 查找所有进程 PID
ps aux | grep postgres | grep -v grep | awk '{print $2}'

# 优雅终止（SIGTERM）
sudo kill -TERM $(ps aux | grep '[p]ostgres' | awk '{print $2}')

# 等待 3 秒
sleep 3

# 强制终止（SIGKILL）
sudo kill -KILL $(ps aux | grep '[p]ostgres' | awk '{print $2}')
```

### 方案3：停止所有服务

```bash
# MacPorts
sudo port unload postgresql16-server

# Homebrew
brew services stop postgresql@16
brew services stop postgresql

# launchd（查找所有相关服务）
sudo launchctl list | grep postgresql | awk '{print $3}' | xargs -I {} sudo launchctl unload {}
```

### 方案4：清理锁文件和共享内存

```bash
# 删除 postmaster.pid
sudo find /opt/local /usr/local /tmp -name "postmaster.pid" -delete

# 删除套接字文件
sudo rm -f /tmp/.s.PGSQL.*

# 清理共享内存（需要 root）
sudo ipcrm -M $(ipcs -m | grep postgres | awk '{print $2}')
```

### 方案5：如果进程无法终止

如果所有方法都无法终止进程，可能需要：

1. **重启系统**（最彻底的方法）

2. **检查是否有守护进程管理器**
   ```bash
   # 检查 supervisord
   supervisorctl status | grep postgres
   
   # 检查 systemd（Linux）
   systemctl status postgresql
   ```

3. **检查是否有其他用户运行的进程**
   ```bash
   # 查看所有用户的进程
   ps aux | grep postgres
   
   # 如果是其他用户，需要切换到该用户或使用 sudo
   sudo -u _postgres pkill postgres
   ```

## 常见问题

### Q1: 为什么 `ps aux | grep postgres` 会匹配到 grep 本身？

A: 这是因为 grep 命令本身包含 "postgres" 字符串。使用以下方式避免：

```bash
# 方法1：使用字符类
ps aux | grep '[p]ostgres'

# 方法2：排除 grep
ps aux | grep postgres | grep -v grep

# 方法3：使用 pgrep
pgrep -a postgres
```

### Q2: 进程显示为 "defunct"（僵尸进程）？

A: 僵尸进程是已终止但父进程未回收的进程。通常可以忽略，但如果很多，可能需要重启系统。

```bash
# 查找僵尸进程
ps aux | grep defunct

# 通常无法直接 kill 僵尸进程，需要 kill 父进程
ps -o ppid= -p <zombie_pid> | xargs kill
```

### Q3: 进程不断重启？

A: 可能是服务管理器自动重启。需要先停止服务：

```bash
# MacPorts
sudo port unload postgresql16-server

# Homebrew
brew services stop postgresql

# launchd
sudo launchctl unload /path/to/plist
```

### Q4: 如何确认进程已完全停止？

A: 使用多种方法验证：

```bash
# 方法1：ps
ps aux | grep '[p]ostgres'

# 方法2：pgrep
pgrep postgres

# 方法3：lsof（检查端口）
sudo lsof -i :5432

# 方法4：netstat
netstat -an | grep 5432
```

### Q5: 卸载后仍有进程，是正常的吗？

A: **不正常**。如果卸载后仍有进程，说明：

1. 卸载不完整
2. 有多个 PostgreSQL 安装
3. 进程没有被正确终止

应该彻底清理所有进程和文件。

## 预防措施

1. **卸载前停止服务**
   ```bash
   sudo port unload postgresql16-server
   ```

2. **使用检查脚本验证**
   ```bash
   ./check_postgres_processes.sh --all
   ```

3. **逐步卸载**
   - 先停止服务
   - 再卸载包
   - 最后删除文件

4. **检查多个安装源**
   - MacPorts
   - Homebrew
   - 手动安装

## 完整清理流程

```bash
# 1. 检查所有进程
./check_postgres_processes.sh --all

# 2. 停止所有服务
sudo port unload postgresql16-server
brew services stop postgresql  # 如果使用 Homebrew

# 3. 终止所有进程
./check_postgres_processes.sh --kill

# 4. 清理残留
./check_postgres_processes.sh --cleanup

# 5. 卸载包
sudo port uninstall postgresql16-server

# 6. 删除文件
./uninstall_postgresql.sh

# 7. 最终验证
./check_postgres_processes.sh --all
```

## 参考资源

- [PostgreSQL 进程管理](https://www.postgresql.org/docs/current/server-shutdown.html)
- [MacPorts 服务管理](https://guide.macports.org/#installing.services)
- [launchd 文档](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/Introduction.html)
