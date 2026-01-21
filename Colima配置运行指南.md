# Colima 配置运行指南

Colima 是一个在 macOS 和 Linux 上运行容器运行时的工具，可以替代 Docker Desktop。它使用 Lima（Linux 虚拟机）来运行容器。

## 目录

1. [安装 Colima](#安装-colima)
2. [基础配置](#基础配置)
3. [启动和停止](#启动和停止)
4. [配置 Docker 镜像加速](#配置-docker-镜像加速)
5. [使用 Docker Compose](#使用-docker-compose)
6. [资源限制配置](#资源限制配置)
7. [常见问题](#常见问题)

---

## 安装 Colima

### macOS

```bash
# 使用 Homebrew 安装
brew install colima docker docker-compose

# 或者使用 Homebrew Cask（包含 Docker CLI）
brew install --cask colima
brew install docker docker-compose
```

### Linux

```bash
# 使用 Homebrew 安装（如果已安装 Homebrew）
brew install colima docker docker-compose

# 或者从 GitHub 下载二进制文件
# https://github.com/abiosoft/colima/releases
```

### 验证安装

```bash
colima version
docker --version
docker-compose --version
```

---

## 基础配置

### 1. 创建 Colima 配置文件（可选）

创建 `~/.colima/default/colima.yaml` 配置文件：

```yaml
# Colima 配置文件
runtime: docker
cpu: 4
memory: 8
disk: 60
arch: host

# 网络配置
network:
  address: true
  dns: []
  
# 挂载配置
mount:
  type: 9p
  location: ~
  
# 环境变量
env:
  DOCKER_BUILDKIT: 1
  COMPOSE_DOCKER_CLI_BUILD: 1
```

### 2. 启动 Colima（使用默认配置）

```bash
# 启动 Colima（默认配置：2 CPU，2GB 内存，60GB 磁盘）
colima start

# 启动时指定配置
colima start --cpu 4 --memory 8 --disk 60

# 启动时指定运行时（docker 或 containerd）
colima start --runtime docker
```

### 3. 验证 Colima 运行状态

```bash
# 查看 Colima 状态
colima status

# 查看 Docker 信息
docker info

# 测试 Docker 是否正常工作
docker run hello-world
```

---

## 启动和停止

### 启动 Colima

```bash
# 使用默认配置启动
colima start

# 使用自定义配置启动
colima start --cpu 4 --memory 8 --disk 60

# 启动时指定名称（可以运行多个实例）
colima start --name my-colima
```

### 停止 Colima

```bash
# 停止 Colima
colima stop

# 停止指定名称的实例
colima stop --name my-colima

# 停止所有实例
colima stop --all
```

### 重启 Colima

```bash
# 重启 Colima
colima restart

# 重启并更新配置
colima restart --cpu 4 --memory 8
```

### 删除 Colima 实例

```bash
# 删除默认实例
colima delete

# 删除指定名称的实例
colima delete --name my-colima

# 删除所有实例
colima delete --all
```

---

## 配置 Docker 镜像加速

### 方法1：在 Colima 启动时配置

```bash
# 停止 Colima
colima stop

# 编辑 Docker daemon 配置
mkdir -p ~/.colima/default/docker
cat > ~/.colima/default/docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
EOF

# 重新启动 Colima
colima start
```

### 方法2：在 Colima 运行后配置

```bash
# 进入 Colima 虚拟机
colima ssh

# 编辑 Docker daemon 配置
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
EOF

# 重启 Docker 服务
sudo systemctl restart docker

# 退出虚拟机
exit

# 重启 Colima（使配置生效）
colima restart
```

### 验证镜像加速配置

```bash
docker info | grep -A 10 "Registry Mirrors"
```

---

## 使用 Docker Compose

### 1. 启动项目服务

```bash
# 确保 Colima 正在运行
colima status

# 进入项目目录
cd /Users/tony/Documents/crypto/corniche

# 启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 2. 停止项目服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

### 3. 单独管理服务

```bash
# 启动特定服务
docker-compose up -d backend
docker-compose up -d frontend

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 重启特定服务
docker-compose restart backend
```

---

## 资源限制配置

### 启动时指定资源

```bash
# 停止当前实例
colima stop

# 使用自定义资源配置启动
colima start \
  --cpu 4 \
  --memory 8 \
  --disk 60 \
  --arch x86_64
```

### 修改现有实例的资源

```bash
# 停止实例
colima stop

# 编辑配置文件（如果存在）
# ~/.colima/default/colima.yaml

# 重新启动（配置会自动应用）
colima start
```

### 查看资源使用情况

```bash
# 查看 Colima 状态
colima status

# 查看 Docker 资源使用
docker stats

# 查看系统资源
colima ssh
free -h
df -h
```

---

## 常见问题

### 1. Colima 启动失败

**问题：** `colima start` 失败

**解决方案：**

```bash
# 检查 Lima 是否正常
lima list

# 删除有问题的实例并重新创建
colima delete
colima start

# 查看详细日志
colima start --debug
```

### 2. Docker 命令无法连接

**问题：** `docker ps` 报错 "Cannot connect to the Docker daemon"

**解决方案：**

```bash
# 检查 Colima 是否运行
colima status

# 如果未运行，启动它
colima start

# 检查 Docker 上下文
docker context ls
docker context use colima
```

### 3. 端口映射不工作

**问题：** 容器端口无法访问

**解决方案：**

```bash
# 检查端口是否被占用
lsof -i :8000
lsof -i :3000

# 检查 Colima 网络配置
colima ssh
ip addr show
exit

# 重启 Colima
colima restart
```

### 4. 磁盘空间不足

**问题：** 磁盘空间不足错误

**解决方案：**

```bash
# 清理 Docker 资源
docker system prune -a --volumes

# 增加 Colima 磁盘大小
colima stop
colima start --disk 100  # 增加到 100GB

# 或者在配置文件中设置
# ~/.colima/default/colima.yaml
# disk: 100
```

### 5. 镜像拉取失败

**问题：** 无法拉取 Docker 镜像

**解决方案：**

```bash
# 配置镜像加速（见上方"配置 Docker 镜像加速"部分）

# 手动拉取镜像
docker pull python:3.11-slim
docker pull node:20-alpine

# 检查网络连接
colima ssh
ping -c 3 docker.io
exit
```

### 6. 文件挂载权限问题

**问题：** 容器内文件权限错误

**解决方案：**

```bash
# 检查挂载点权限
ls -la /path/to/mount

# 在 Colima 配置中设置挂载选项
# ~/.colima/default/colima.yaml
# mount:
#   type: 9p
#   location: ~
#   writable: true
```

---

## 高级配置

### 1. 多实例运行

```bash
# 启动多个 Colima 实例
colima start --name dev --cpu 2 --memory 4
colima start --name prod --cpu 4 --memory 8

# 切换 Docker 上下文
docker context use colima-dev
docker context use colima-prod

# 查看所有实例
colima list
```

### 2. 使用 Kubernetes

```bash
# 启动带 Kubernetes 的 Colima
colima start --kubernetes

# 验证 Kubernetes
kubectl get nodes

# 停止 Kubernetes
colima stop
```

### 3. 网络配置

```bash
# 启动时配置网络
colima start --network-address

# 在配置文件中设置
# ~/.colima/default/colima.yaml
# network:
#   address: true
#   dns:
#     - 8.8.8.8
#     - 8.8.4.4
```

---

## 与本项目集成

### 快速启动项目

```bash
# 1. 启动 Colima
colima start --cpu 4 --memory 8 --disk 60

# 2. 配置镜像加速（可选，但推荐）
# 按照上方"配置 Docker 镜像加速"部分操作

# 3. 进入项目目录
cd /Users/tony/Documents/crypto/corniche

# 4. 启动所有服务
docker-compose up -d --build

# 5. 查看服务状态
docker-compose ps

# 6. 查看日志
docker-compose logs -f
```

### 停止项目

```bash
# 停止所有服务
docker-compose down

# 停止 Colima（可选）
colima stop
```

---

## 性能优化建议

1. **资源配置：**
   - CPU: 至少 2 核，推荐 4 核
   - 内存: 至少 4GB，推荐 8GB
   - 磁盘: 至少 40GB，推荐 60GB+

2. **镜像加速：**
   - 必须配置镜像加速器，否则拉取镜像会很慢

3. **资源清理：**
   - 定期清理未使用的镜像和容器
   - `docker system prune -a --volumes`

4. **网络优化：**
   - 使用 `--network-address` 启用网络地址
   - 配置 DNS 服务器

---

## 参考资源

- Colima 官方文档: https://github.com/abiosoft/colima
- Lima 官方文档: https://github.com/lima-vm/lima
- Docker 官方文档: https://docs.docker.com/

---

## 总结

Colima 是一个轻量级的 Docker Desktop 替代方案，特别适合 macOS 用户。通过本指南，你应该能够：

1. ✅ 安装和配置 Colima
2. ✅ 启动和停止 Colima
3. ✅ 配置 Docker 镜像加速
4. ✅ 使用 Docker Compose 运行项目
5. ✅ 解决常见问题

如果遇到问题，请查看 Colima 日志：
```bash
colima start --debug
```
