# 解决 Docker 内网IP连接问题

## 问题分析

`172.23.0.2` 是 Docker 容器的内网IP，无法从外部直接通过SSH访问。

## 解决方案

### 方案1: 使用 Docker 宿主机IP（推荐）

#### 步骤1: 查找宿主机IP

**在服务器上执行：**

```bash
# 方法1: 查看宿主机公网IP
curl ifconfig.me

# 方法2: 查看宿主机内网IP
hostname -I

# 方法3: 查看Docker网络信息
docker network inspect bridge | grep Gateway
```

#### 步骤2: 使用宿主机IP连接

```bash
# 使用宿主机IP（公网或内网）
scp crypto_data.db root@宿主机IP:/opt/corniche/data/

# 如果SSH端口不是22，指定端口
scp -P 2222 crypto_data.db root@宿主机IP:/opt/corniche/data/
```

---

### 方案2: 使用 docker cp 命令（最简单）

**如果可以直接访问Docker宿主机：**

```bash
# 1. 上传到宿主机临时目录
scp crypto_data.db root@宿主机IP:/tmp/

# 2. SSH登录到宿主机
ssh root@宿主机IP

# 3. 使用docker cp复制到容器
docker cp /tmp/crypto_data.db container_name:/opt/corniche/data/

# 或使用容器ID
docker cp /tmp/crypto_data.db $(docker ps | grep corniche | awk '{print $1}'):/opt/corniche/data/
```

**一键命令：**

```bash
# 上传并复制（需要先配置SSH密钥）
scp crypto_data.db root@宿主机IP:/tmp/ && \
ssh root@宿主机IP "docker cp /tmp/crypto_data.db \$(docker ps -q -f name=corniche):/opt/corniche/data/ && rm /tmp/crypto_data.db"
```

---

### 方案3: 通过 Docker Volume 挂载

**如果使用 Docker Compose，数据目录已挂载：**

```bash
# 1. 上传到宿主机挂载目录
scp crypto_data.db root@宿主机IP:/opt/corniche/data/

# 2. 重启容器（如果需要）
ssh root@宿主机IP "cd /opt/corniche && docker-compose restart"
```

---

### 方案4: 在容器内启动SSH服务

**在Docker容器内安装SSH服务：**

```bash
# 1. 进入容器
docker exec -it container_name /bin/bash

# 2. 安装SSH服务
apt-get update
apt-get install -y openssh-server

# 3. 配置SSH
echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# 4. 设置root密码
passwd root

# 5. 启动SSH服务
service ssh start

# 6. 映射SSH端口（在docker-compose.yml中添加）
ports:
  - "2222:22"
```

**然后使用映射端口连接：**

```bash
scp -P 2222 crypto_data.db root@宿主机IP:/opt/corniche/data/
```

---

### 方案5: 使用 rsync（如果SSH可用）

```bash
# 使用rsync（可能更稳定）
rsync -avz --progress -e "ssh -p 2222" \
  crypto_data.db root@宿主机IP:/opt/corniche/data/
```

---

## 快速操作步骤

### 推荐流程（最简单）

```bash
# 1. 查找宿主机IP（在服务器上执行）
curl ifconfig.me  # 公网IP

# 2. 上传到宿主机
scp crypto_data.db root@宿主机公网IP:/tmp/

# 3. 复制到容器
ssh root@宿主机公网IP "docker cp /tmp/crypto_data.db \$(docker ps -q -f name=corniche):/opt/corniche/data/"
```

---

## 查找容器和宿主机信息

### 查找容器名称

```bash
# 在宿主机上
docker ps | grep corniche

# 查看容器详细信息
docker inspect $(docker ps -q -f name=corniche) | grep -A 10 "NetworkSettings"
```

### 查找宿主机IP

```bash
# 公网IP
curl ifconfig.me

# 内网IP
hostname -I

# Docker网关（通常是宿主机IP）
docker network inspect bridge | grep Gateway
```

---

## 完整示例脚本

创建 `upload_db_to_docker.sh`:

```bash
#!/bin/bash

# 数据库文件上传到Docker容器脚本

DB_FILE="data/crypto_data.db"
HOST_IP="${1:-请提供宿主机IP}"
CONTAINER_NAME="${2:-corniche}"

if [ "$HOST_IP" = "请提供宿主机IP" ]; then
    echo "用法: $0 <宿主机IP> [容器名称]"
    echo "示例: $0 47.xxx.xxx.xxx corniche"
    exit 1
fi

echo "=== 上传数据库文件到Docker容器 ==="
echo "宿主机IP: $HOST_IP"
echo "容器名称: $CONTAINER_NAME"
echo ""

# 1. 上传到宿主机临时目录
echo "1. 上传文件到宿主机..."
scp "$DB_FILE" root@$HOST_IP:/tmp/crypto_data.db

# 2. 复制到容器
echo "2. 复制文件到容器..."
ssh root@$HOST_IP "docker cp /tmp/crypto_data.db \$(docker ps -q -f name=$CONTAINER_NAME):/opt/corniche/data/"

# 3. 清理临时文件
echo "3. 清理临时文件..."
ssh root@$HOST_IP "rm /tmp/crypto_data.db"

echo "✓ 完成！"
```

使用：

```bash
chmod +x upload_db_to_docker.sh
./upload_db_to_docker.sh 47.xxx.xxx.xxx corniche
```

---

## 常见问题

### Q1: 如何找到Docker宿主机IP？

```bash
# 在服务器上执行
curl ifconfig.me  # 公网IP
hostname -I       # 内网IP
```

### Q2: 如何找到容器名称？

```bash
docker ps | grep corniche
```

### Q3: 容器内没有SSH服务怎么办？

使用 `docker cp` 命令，不需要SSH服务。

### Q4: 权限问题？

```bash
# 在宿主机上设置权限
ssh root@宿主机IP "chmod 644 /opt/corniche/data/crypto_data.db"
```

---

## 总结

**最简单的解决方法：**

```bash
# 1. 找到宿主机IP
# 在服务器上: curl ifconfig.me

# 2. 上传到宿主机
scp crypto_data.db root@宿主机IP:/tmp/

# 3. 复制到容器
ssh root@宿主机IP "docker cp /tmp/crypto_data.db \$(docker ps -q -f name=corniche):/opt/corniche/data/"
```
