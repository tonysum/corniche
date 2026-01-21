# PostgreSQL 连接问题解决指南

## 错误信息

```
psql error: connection to server socket "/tmp/.s.PGSQL.5432" failed: No such file or directory
```

## 问题原因

这个错误通常表示：

1. **PostgreSQL 服务未运行**（最常见）
2. **套接字文件路径配置不正确**
3. **权限问题**
4. **服务启动失败**

## 快速诊断

### 使用诊断脚本

```bash
# 完整诊断
./fix_postgresql_connection.sh

# 自动修复
./fix_postgresql_connection.sh --fix
```

### 手动检查

```bash
# 1. 检查服务是否运行
ps aux | grep '[p]ostgres'

# 2. 检查端口是否监听
lsof -i :5432

# 3. 检查套接字文件
ls -la /tmp/.s.PGSQL.*

# 4. 检查服务状态（MacPorts）
sudo port installed postgresql15-server
```

## 解决方案

### 方案1：启动 PostgreSQL 服务（最常见）

```bash
# 使用 MacPorts 启动
sudo port load postgresql15-server

# 等待几秒后检查
ps aux | grep '[p]ostgres'
```

### 方案2：检查服务状态

```bash
# 检查 MacPorts 服务
sudo port installed postgresql15-server

# 检查 launchd 服务
launchctl list | grep postgresql

# 检查进程
ps aux | grep postgres
```

### 方案3：使用 TCP/IP 连接（临时解决方案）

如果 Unix 套接字不可用，可以使用 TCP/IP：

```bash
# 使用 localhost 连接
psql -h localhost -U _postgres -d postgres

# 或指定端口
psql -h localhost -p 5432 -U _postgres -d postgres
```

### 方案4：修复套接字配置

编辑 PostgreSQL 配置文件：

```bash
# 找到配置文件
sudo nano /opt/local/etc/postgresql15/postgresql.conf
# 或
sudo nano /opt/local/var/db/postgresql15/defaultdb/postgresql.conf
```

添加或修改：

```conf
# Unix socket directories
unix_socket_directories = '/tmp'

# 或使用其他目录
unix_socket_directories = '/opt/local/var/run/postgresql15'
```

然后重启服务：

```bash
sudo port unload postgresql15-server
sudo port load postgresql15-server
```

### 方案5：创建套接字目录

```bash
# 创建目录
sudo mkdir -p /opt/local/var/run/postgresql15
sudo chmod 1777 /opt/local/var/run/postgresql15
sudo chown _postgres:_postgres /opt/local/var/run/postgresql15

# 确保 /tmp 权限正确
sudo chmod 1777 /tmp
```

## 详细诊断步骤

### 步骤1：检查服务是否运行

```bash
# 检查进程
ps aux | grep '[p]ostgres'

# 应该看到类似输出：
# _postgres  ... postgres: postmaster ...
```

如果没有输出，服务未运行。

### 步骤2：检查端口监听

```bash
# 检查端口
lsof -i :5432

# 或使用 netstat
netstat -an | grep 5432
```

如果没有输出，服务未监听端口。

### 步骤3：检查套接字文件

```bash
# 查找套接字文件
find /tmp /opt/local/var/run -name ".s.PGSQL.*" 2>/dev/null

# 检查 /tmp 权限
ls -ld /tmp
# 应该是 drwxrwxrwt
```

### 步骤4：检查配置文件

```bash
# 查看 unix_socket_directories 设置
sudo grep -E "unix_socket|port" /opt/local/etc/postgresql15/postgresql.conf

# 查看数据目录配置
sudo grep "data_directory" /opt/local/etc/postgresql15/postgresql.conf
```

### 步骤5：查看日志

```bash
# 查看 PostgreSQL 日志
tail -f /opt/local/var/log/postgresql15/postgresql.log

# 或系统日志
tail -f /var/log/system.log | grep postgres
```

## 常见问题

### Q1: 服务启动失败

**可能原因：**
- 数据目录不存在或权限错误
- 配置文件有错误
- 端口被占用

**解决方法：**
```bash
# 检查数据目录
ls -la /opt/local/var/db/postgresql15/defaultdb

# 检查权限
sudo chown -R _postgres:_postgres /opt/local/var/db/postgresql15/defaultdb
sudo chmod 700 /opt/local/var/db/postgresql15/defaultdb

# 检查端口占用
lsof -i :5432
```

### Q2: 套接字文件权限错误

**解决方法：**
```bash
# 确保 /tmp 权限正确
sudo chmod 1777 /tmp

# 或使用其他目录
sudo mkdir -p /opt/local/var/run/postgresql15
sudo chmod 1777 /opt/local/var/run/postgresql15
```

### Q3: 连接被拒绝

**可能原因：**
- pg_hba.conf 配置问题
- 防火墙阻止

**解决方法：**
```bash
# 检查 pg_hba.conf
sudo cat /opt/local/etc/postgresql15/pg_hba.conf | grep -v "^#"

# 添加本地连接规则
sudo nano /opt/local/etc/postgresql15/pg_hba.conf
# 添加: local    all    all    trust
```

### Q4: 服务启动后立即退出

**解决方法：**
```bash
# 查看详细日志
tail -50 /opt/local/var/log/postgresql15/postgresql.log

# 手动启动查看错误
sudo su _postgres -c '/opt/local/lib/postgresql15/bin/postgres -D /opt/local/var/db/postgresql15/defaultdb'
```

## 验证连接

### 方法1：使用 Unix 套接字

```bash
psql -d postgres
# 或
sudo su _postgres -c 'psql -d postgres'
```

### 方法2：使用 TCP/IP

```bash
psql -h localhost -U _postgres -d postgres
```

### 方法3：指定套接字路径

```bash
psql -h /tmp -d postgres
# 或
psql -h /opt/local/var/run/postgresql15 -d postgres
```

## 预防措施

1. **确保服务自动启动**
   ```bash
   sudo port load postgresql15-server
   ```

2. **检查启动脚本**
   ```bash
   # MacPorts launchd 配置
   cat /opt/local/Library/LaunchDaemons/org.macports.postgresql15-server.plist
   ```

3. **监控服务状态**
   ```bash
   # 添加到 crontab 或监控脚本
   ps aux | grep '[p]ostgres' || sudo port load postgresql15-server
   ```

## 参考资源

- [PostgreSQL 连接文档](https://www.postgresql.org/docs/current/client-authentication.html)
- [Unix 套接字配置](https://www.postgresql.org/docs/current/runtime-config-connection.html)
