# PostgreSQL 访问配置指南

## 问题描述

错误信息：
```
no pg_hba.conf entry for host "192.168.2.102", user "tony", database "postgres", no encryption
```

这个错误表示 PostgreSQL 的 `pg_hba.conf` 文件中没有允许来自 IP `192.168.2.102` 的用户 `tony` 连接到 `postgres` 数据库的规则。

## 快速解决方案

### 方法1：使用配置脚本（推荐）

```bash
# 允许特定 IP 访问
./configure_pg_hba.sh --ip 192.168.2.102 --user tony --database postgres --auth md5

# 或者允许整个局域网访问
./configure_pg_hba.sh --lan --auth md5
```

### 方法2：手动编辑配置文件

1. **找到 pg_hba.conf 文件**

   MacPorts 安装的 PostgreSQL 16，配置文件通常在：
   ```bash
   /opt/local/etc/postgresql16/pg_hba.conf
   ```

   如果找不到，可以查找：
   ```bash
   sudo find /opt/local -name "pg_hba.conf" 2>/dev/null
   ```

2. **备份配置文件**

   ```bash
   sudo cp /opt/local/etc/postgresql16/pg_hba.conf /opt/local/etc/postgresql16/pg_hba.conf.backup
   ```

3. **编辑配置文件**

   ```bash
   sudo nano /opt/local/etc/postgresql16/pg_hba.conf
   ```

4. **添加访问规则**

   在文件末尾添加以下行之一：

   **选项 A：允许特定 IP（推荐）**
   ```
   host    postgres    tony    192.168.2.102/32    md5
   ```

   **选项 B：允许整个局域网**
   ```
   host    all    all    192.168.0.0/16    md5
   ```

   **选项 C：允许所有 IP（不安全，仅用于开发环境）**
   ```
   host    all    all    0.0.0.0/0    md5
   ```

5. **重新加载配置**

   ```bash
   # 方法1：重新加载配置（不中断服务）
   sudo su _postgres -c '/opt/local/lib/postgresql16/bin/pg_ctl -D /opt/local/var/db/postgresql16/defaultdb reload'

   # 方法2：重启服务
   sudo port unload postgresql16-server
   sudo port load postgresql16-server
   ```

## pg_hba.conf 配置说明

### 配置格式

```
连接类型    数据库    用户    地址    认证方法
```

### 连接类型

- `local` - Unix 域套接字连接
- `host` - TCP/IP 连接（SSL 或非 SSL）
- `hostssl` - SSL 加密的 TCP/IP 连接
- `hostnossl` - 非 SSL 的 TCP/IP 连接

### 地址格式

- 单个 IP: `192.168.2.102/32`
- CIDR 网段: `192.168.0.0/16`
- 所有地址: `0.0.0.0/0` 或 `all`
- 主机名: `example.com`

### 认证方法

- `trust` - 无需密码（仅用于本地，不安全）
- `md5` - MD5 加密密码（旧方法，兼容性好）
- `scram-sha-256` - SCRAM-SHA-256 加密（推荐，PostgreSQL 10+）
- `password` - 明文密码（不安全，不推荐）
- `peer` - 使用操作系统用户名（仅 local）
- `ident` - 使用 ident 协议

## 常见配置示例

### 1. 允许本地连接（无密码）

```
local    all    all    trust
host    all    all    127.0.0.1/32    trust
host    all    all    ::1/128    trust
```

### 2. 允许局域网访问（需要密码）

```
host    all    all    192.168.0.0/16    md5
```

### 3. 允许特定 IP 访问特定数据库

```
host    crypto_data    crypto_user    192.168.2.102/32    scram-sha-256
```

### 4. 允许 SSL 连接

```
hostssl    all    all    0.0.0.0/0    scram-sha-256
```

### 5. 允许非 SSL 连接（开发环境）

```
hostnossl    all    all    192.168.0.0/16    md5
```

## 解决 "no encryption" 错误

如果错误信息包含 "no encryption"，有两种解决方案：

### 方案1：允许非 SSL 连接（开发环境）

在 `pg_hba.conf` 中添加：

```
hostnossl    postgres    tony    192.168.2.102/32    md5
```

### 方案2：启用 SSL 连接（生产环境推荐）

1. **配置 SSL**

   编辑 `postgresql.conf`：
   ```bash
   sudo nano /opt/local/etc/postgresql16/postgresql.conf
   ```

   添加或修改：
   ```
   ssl = on
   ssl_cert_file = 'server.crt'
   ssl_key_file = 'server.key'
   ```

2. **生成 SSL 证书（自签名）**

   ```bash
   cd /opt/local/var/db/postgresql16/defaultdb
   sudo su _postgres -c 'openssl req -new -x509 -days 365 -nodes -text -out server.crt -keyout server.key -subj "/CN=dbhost.yourdomain.com"'
   sudo chmod 600 server.key
   sudo chown _postgres:_postgres server.crt server.key
   ```

3. **配置 pg_hba.conf**

   ```
   hostssl    postgres    tony    192.168.2.102/32    scram-sha-256
   ```

4. **客户端连接时使用 SSL**

   ```bash
   psql "host=192.168.2.102 port=5432 dbname=postgres user=tony sslmode=require"
   ```

## 验证配置

### 1. 检查配置文件语法

```bash
sudo su _postgres -c '/opt/local/lib/postgresql16/bin/pg_ctl -D /opt/local/var/db/postgresql16/defaultdb -t 5 -o "-c hba_file=/opt/local/etc/postgresql16/pg_hba.conf" configtest'
```

### 2. 查看当前配置

```bash
# 使用脚本查看
./configure_pg_hba.sh --show

# 或直接查看文件
sudo cat /opt/local/etc/postgresql16/pg_hba.conf | grep -v "^#" | grep -v "^$"
```

### 3. 测试连接

```bash
# 从客户端测试
psql -h 192.168.2.102 -p 5432 -U tony -d postgres

# 或指定密码
PGPASSWORD=your_password psql -h 192.168.2.102 -p 5432 -U tony -d postgres
```

## 安全建议

1. **最小权限原则**
   - 只允许必要的 IP 访问
   - 使用强密码认证
   - 避免使用 `trust` 认证方法

2. **使用 SSL**
   - 生产环境必须启用 SSL
   - 使用 `hostssl` 而不是 `host`
   - 使用 `scram-sha-256` 认证方法

3. **网络隔离**
   - 使用防火墙限制访问
   - 只允许内网访问
   - 避免暴露到公网

4. **定期审查**
   - 定期检查 `pg_hba.conf` 配置
   - 移除不必要的访问规则
   - 监控连接日志

## 故障排除

### 问题1：配置后仍然无法连接

**检查项：**
1. 配置文件路径是否正确
2. 配置是否已重新加载
3. PostgreSQL 服务是否运行
4. 防火墙是否阻止连接
5. 用户是否存在且有权限

**调试命令：**
```bash
# 检查服务状态
sudo port installed postgresql16-server
ps aux | grep postgres

# 检查日志
tail -f /opt/local/var/log/postgresql16/postgresql.log

# 检查用户
sudo su _postgres -c "psql -d postgres -c '\du'"
```

### 问题2：配置文件语法错误

如果配置文件有语法错误，PostgreSQL 可能无法启动。检查日志：

```bash
tail -f /opt/local/var/log/postgresql16/postgresql.log
```

### 问题3：权限被拒绝

确保：
1. 用户存在：`CREATE USER tony WITH PASSWORD 'password';`
2. 用户有数据库权限：`GRANT ALL PRIVILEGES ON DATABASE postgres TO tony;`
3. `pg_hba.conf` 中有对应规则

## 参考资源

- [PostgreSQL pg_hba.conf 文档](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html)
- [PostgreSQL 认证方法](https://www.postgresql.org/docs/current/auth-methods.html)
- [PostgreSQL SSL 配置](https://www.postgresql.org/docs/current/ssl-tcp.html)
