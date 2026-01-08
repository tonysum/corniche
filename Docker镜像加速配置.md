# Docker 镜像加速配置

## 问题说明

如果遇到 `ERROR [internal] load metadata for docker.io/library/node:20-alpine` 或类似的错误，通常是无法连接到 Docker Hub 导致的。

## 解决方案

### 方案1：配置 Docker 镜像加速器（推荐）

#### macOS / Windows Desktop

1. 打开 Docker Desktop
2. 进入 Settings（设置）→ Docker Engine
3. 在 JSON 配置中添加镜像加速器：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
```

4. 点击 "Apply & Restart" 应用并重启

#### Linux

编辑或创建 `/etc/docker/daemon.json`：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 方案2：使用国内镜像源（修改 Dockerfile）

如果无法配置镜像加速器，可以修改 Dockerfile 使用国内镜像源。

#### 修改后端 Dockerfile

将 `Dockerfile.backend` 中的基础镜像改为：

```dockerfile
FROM registry.cn-hangzhou.aliyuncs.com/acs/python:3.11-slim
```

或者使用其他国内镜像源。

#### 修改前端 Dockerfile

将 `frontend/Dockerfile` 中的基础镜像改为：

```dockerfile
FROM registry.cn-hangzhou.aliyuncs.com/acs/node:20-alpine
```

### 方案3：手动拉取镜像

```bash
# 拉取后端基础镜像
docker pull python:3.11-slim

# 拉取前端基础镜像
docker pull node:20-alpine

# 然后再构建
docker-compose up -d --build
```

### 方案4：检查网络连接

```bash
# 测试 Docker Hub 连接
curl -I https://hub.docker.com

# 测试能否拉取镜像
docker pull hello-world
```

## 验证配置

配置完成后，验证是否生效：

```bash
docker info | grep -A 10 "Registry Mirrors"
```

应该能看到配置的镜像加速器地址。

## 重新构建

配置完成后，重新构建：

```bash
docker-compose down
docker-compose up -d --build
```

