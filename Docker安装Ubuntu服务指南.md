# Docker 安装 Ubuntu 服务操作指南

## 目录
1. [前置要求](#前置要求)
2. [基础操作](#基础操作)
3. [常用场景](#常用场景)
4. [数据持久化](#数据持久化)
5. [网络配置](#网络配置)
6. [高级用法](#高级用法)
7. [故障排查](#故障排查)

---

## 前置要求

### 1. 安装 Docker

**macOS:**
```bash
# 使用 Homebrew 安装
brew install --cask docker

# 或者下载 Docker Desktop
# https://www.docker.com/products/docker-desktop
```

**Linux (Ubuntu/Debian):**
```bash
# 更新软件包索引
sudo apt-get update

# 安装必要的依赖
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# 添加 Docker 官方 GPG 密钥
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 设置仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到 docker 组（避免每次使用 sudo）
sudo usermod -aG docker $USER
# 重新登录后生效
```

**验证安装:**
```bash
docker --version
docker-compose --version
```

---

## 基础操作

### 1. 拉取 Ubuntu 镜像

```bash
# 拉取最新版 Ubuntu
docker pull ubuntu:latest

# 拉取指定版本（推荐，更稳定）
docker pull ubuntu:22.04
docker pull ubuntu:20.04

# 查看本地镜像
docker images
```

### 2. 运行 Ubuntu 容器

**基础运行（交互式）:**
```bash
# 运行并进入容器（退出后容器停止）
docker run -it ubuntu:22.04 /bin/bash

# 运行并保持后台运行
docker run -d --name my-ubuntu ubuntu:22.04 sleep infinity
```

**常用参数说明:**
- `-it`: 交互式终端
- `-d`: 后台运行（detached）
- `--name`: 指定容器名称
- `-p`: 端口映射（格式：主机端口:容器端口）
- `-v`: 数据卷挂载（格式：主机路径:容器路径）
- `-e`: 设置环境变量
- `--restart`: 重启策略

### 3. 进入运行中的容器

```bash
# 方式1：使用 exec（推荐）
docker exec -it my-ubuntu /bin/bash

# 方式2：使用 attach（不推荐，退出会停止容器）
docker attach my-ubuntu
```

### 4. 容器管理命令

```bash
# 查看运行中的容器
docker ps

# 查看所有容器（包括已停止）
docker ps -a

# 启动容器
docker start my-ubuntu

# 停止容器
docker stop my-ubuntu

# 重启容器
docker restart my-ubuntu

# 删除容器（需先停止）
docker rm my-ubuntu

# 强制删除运行中的容器
docker rm -f my-ubuntu

# 查看容器日志
docker logs my-ubuntu
docker logs -f my-ubuntu  # 实时查看日志

# 查看容器资源使用情况
docker stats my-ubuntu
```

---

## 常用场景

### 场景1: 运行一个持久的 Ubuntu 服务器

```bash
# 创建并运行容器
docker run -d \
  --name ubuntu-server \
  --restart unless-stopped \
  -p 2222:22 \
  -v /host/data:/root/data \
  ubuntu:22.04 \
  sleep infinity

# 进入容器安装 SSH 服务
docker exec -it ubuntu-server /bin/bash

# 在容器内执行：
apt-get update
apt-get install -y openssh-server vim curl wget
service ssh start
```

### 场景2: 运行带 Web 服务的 Ubuntu

```bash
# 运行容器并映射端口
docker run -d \
  --name ubuntu-web \
  -p 8080:80 \
  -v $(pwd)/html:/var/www/html \
  ubuntu:22.04 \
  sleep infinity

# 进入容器安装 Nginx
docker exec -it ubuntu-web /bin/bash
apt-get update && apt-get install -y nginx
service nginx start
```

### 场景3: 运行开发环境

```bash
# 运行开发容器
docker run -d \
  --name ubuntu-dev \
  -p 3000:3000 \
  -v $(pwd)/code:/workspace \
  -e NODE_ENV=development \
  ubuntu:22.04 \
  sleep infinity

# 进入容器安装开发工具
docker exec -it ubuntu-dev /bin/bash
apt-get update
apt-get install -y nodejs npm python3 python3-pip git
```

### 场景4: 运行数据库服务

```bash
# 运行 MySQL
docker run -d \
  --name mysql-server \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=yourpassword \
  -e MYSQL_DATABASE=mydb \
  -v mysql_data:/var/lib/mysql \
  mysql:8.0

# 运行 PostgreSQL
docker run -d \
  --name postgres-server \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=mydb \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15
```

---

## 数据持久化

### 1. 使用数据卷（Volume）

```bash
# 创建数据卷
docker volume create mydata

# 使用数据卷
docker run -d \
  --name ubuntu-data \
  -v mydata:/data \
  ubuntu:22.04 \
  sleep infinity

# 查看数据卷
docker volume ls
docker volume inspect mydata

# 删除数据卷
docker volume rm mydata
```

### 2. 使用绑定挂载（Bind Mount）

```bash
# 挂载主机目录到容器
docker run -d \
  --name ubuntu-bind \
  -v /host/path:/container/path \
  -v $(pwd)/data:/app/data \
  ubuntu:22.04 \
  sleep infinity
```

### 3. 只读挂载

```bash
# 挂载为只读
docker run -d \
  --name ubuntu-readonly \
  -v /host/path:/container/path:ro \
  ubuntu:22.04 \
  sleep infinity
```

---

## 网络配置

### 1. 查看网络

```bash
# 查看所有网络
docker network ls

# 查看网络详情
docker network inspect bridge
```

### 2. 创建自定义网络

```bash
# 创建网络
docker network create mynetwork

# 使用自定义网络运行容器
docker run -d \
  --name ubuntu-net \
  --network mynetwork \
  ubuntu:22.04 \
  sleep infinity

# 连接容器到网络
docker network connect mynetwork existing-container
```

### 3. 容器间通信

```bash
# 在同一网络中，容器可以通过名称互相访问
docker run -d --name container1 --network mynetwork ubuntu:22.04
docker run -d --name container2 --network mynetwork ubuntu:22.04

# container2 可以通过 container1 访问 container1
docker exec -it container2 ping container1
```

### 4. 端口映射

```bash
# 映射单个端口
docker run -d -p 8080:80 ubuntu:22.04

# 映射多个端口
docker run -d -p 8080:80 -p 2222:22 ubuntu:22.04

# 指定主机 IP
docker run -d -p 127.0.0.1:8080:80 ubuntu:22.04

# 随机端口映射
docker run -d -p 80 ubuntu:22.04
```

---

## 高级用法

### 1. 使用 Docker Compose

创建 `docker-compose.yml`:

```yaml
version: '3.8'

services:
  ubuntu-service:
    image: ubuntu:22.04
    container_name: my-ubuntu
    ports:
      - "8080:80"
      - "2222:22"
    volumes:
      - ./data:/app/data
      - app_data:/app/storage
    environment:
      - ENV_VAR=value
    restart: unless-stopped
    command: sleep infinity
    networks:
      - app-network

volumes:
  app_data:

networks:
  app-network:
    driver: bridge
```

运行:
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

### 2. 自定义 Dockerfile

创建 `Dockerfile`:

```dockerfile
FROM ubuntu:22.04

# 设置工作目录
WORKDIR /app

# 更新并安装软件
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    curl \
    wget \
    vim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 复制文件
COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python3", "app.py"]
```

构建和运行:
```bash
# 构建镜像
docker build -t my-ubuntu-app .

# 运行容器
docker run -d -p 8000:8000 my-ubuntu-app
```

### 3. 资源限制

```bash
# 限制内存和 CPU
docker run -d \
  --name ubuntu-limited \
  --memory="512m" \
  --cpus="1.0" \
  ubuntu:22.04 \
  sleep infinity

# 查看资源使用
docker stats ubuntu-limited
```

### 4. 环境变量

```bash
# 设置环境变量
docker run -d \
  --name ubuntu-env \
  -e VAR1=value1 \
  -e VAR2=value2 \
  ubuntu:22.04 \
  sleep infinity

# 使用环境变量文件
docker run -d \
  --name ubuntu-env-file \
  --env-file .env \
  ubuntu:22.04 \
  sleep infinity
```

### 5. 健康检查

```bash
docker run -d \
  --name ubuntu-healthy \
  --health-cmd="curl -f http://localhost || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  ubuntu:22.04 \
  sleep infinity

# 查看健康状态
docker ps
```

---

## 故障排查

### 1. 容器无法启动

```bash
# 查看容器日志
docker logs container-name

# 查看详细错误信息
docker inspect container-name

# 以前台模式运行查看错误
docker run -it ubuntu:22.04 /bin/bash
```

### 2. 端口冲突

```bash
# 查看端口占用
# macOS/Linux
lsof -i :8080
netstat -tulpn | grep 8080

# 修改端口映射
docker run -d -p 8081:80 ubuntu:22.04
```

### 3. 权限问题

```bash
# 查看容器内文件权限
docker exec -it container-name ls -la /path

# 修改权限
docker exec -it container-name chmod 755 /path
docker exec -it container-name chown user:group /path
```

### 4. 数据丢失

```bash
# 检查数据卷
docker volume ls
docker volume inspect volume-name

# 备份数据卷
docker run --rm \
  -v volume-name:/data \
  -v $(pwd):/backup \
  ubuntu:22.04 \
  tar czf /backup/backup.tar.gz /data

# 恢复数据卷
docker run --rm \
  -v volume-name:/data \
  -v $(pwd):/backup \
  ubuntu:22.04 \
  tar xzf /backup/backup.tar.gz -C /
```

### 5. 网络问题

```bash
# 测试容器网络
docker exec -it container-name ping google.com

# 检查 DNS 配置
docker exec -it container-name cat /etc/resolv.conf

# 重启网络
docker network disconnect network-name container-name
docker network connect network-name container-name
```

### 6. 清理资源

```bash
# 停止所有容器
docker stop $(docker ps -aq)

# 删除所有停止的容器
docker rm $(docker ps -aq)

# 删除未使用的镜像
docker image prune -a

# 删除未使用的数据卷
docker volume prune

# 删除未使用的网络
docker network prune

# 清理所有未使用的资源
docker system prune -a --volumes
```

---

## 实用脚本示例

### 快速启动 Ubuntu 开发环境

创建 `start-ubuntu-dev.sh`:

```bash
#!/bin/bash

CONTAINER_NAME="ubuntu-dev"
IMAGE="ubuntu:22.04"

# 检查容器是否存在
if docker ps -a | grep -q $CONTAINER_NAME; then
    echo "容器已存在，启动中..."
    docker start $CONTAINER_NAME
else
    echo "创建新容器..."
    docker run -d \
        --name $CONTAINER_NAME \
        -p 2222:22 \
        -v $(pwd):/workspace \
        -v ubuntu_dev_data:/root \
        --restart unless-stopped \
        $IMAGE \
        sleep infinity
fi

# 进入容器
docker exec -it $CONTAINER_NAME /bin/bash
```

### 备份容器数据

创建 `backup-container.sh`:

```bash
#!/bin/bash

CONTAINER_NAME=$1
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

docker exec $CONTAINER_NAME tar czf - /data | \
    cat > $BACKUP_DIR/${CONTAINER_NAME}_${TIMESTAMP}.tar.gz

echo "备份完成: $BACKUP_DIR/${CONTAINER_NAME}_${TIMESTAMP}.tar.gz"
```

---

## 最佳实践

1. **使用特定版本标签**: 不要使用 `latest`，使用具体版本如 `ubuntu:22.04`
2. **设置重启策略**: 使用 `--restart unless-stopped` 确保容器自动重启
3. **数据持久化**: 重要数据使用数据卷或绑定挂载
4. **资源限制**: 生产环境设置内存和 CPU 限制
5. **日志管理**: 配置日志驱动和日志轮转
6. **安全**: 不要以 root 用户运行应用，使用非特权用户
7. **多阶段构建**: 使用多阶段构建减小镜像大小
8. **健康检查**: 为服务添加健康检查机制

---

## 参考资源

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Hub Ubuntu 镜像](https://hub.docker.com/_/ubuntu)
- [Docker Compose 文档](https://docs.docker.com/compose/)

---

## 常见问题 FAQ

**Q: 如何让容器在后台持续运行？**
A: 使用 `sleep infinity` 或运行一个长期运行的服务

**Q: 如何查看容器占用的磁盘空间？**
A: `docker system df`

**Q: 如何进入已停止的容器？**
A: 先启动容器 `docker start container-name`，然后 `docker exec -it container-name /bin/bash`

**Q: 容器内的数据会丢失吗？**
A: 如果不使用数据卷或绑定挂载，容器删除后数据会丢失

**Q: 如何更新容器内的软件？**
A: 进入容器后使用 `apt-get update && apt-get upgrade`，或重新构建镜像
