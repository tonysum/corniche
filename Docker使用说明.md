# Docker 部署说明

## 前置要求

- 安装 Docker 和 Docker Compose
- 确保端口 8000 和 3000 未被占用
- **如果遇到镜像拉取失败，请参考 `Docker镜像加速配置.md` 配置镜像加速器**

## 快速开始

### 1. 构建和启动所有服务

```bash
docker-compose up -d --build
```

### 2. 查看服务状态

```bash
docker-compose ps
```

### 3. 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看后端日志
docker-compose logs -f backend

# 查看前端日志
docker-compose logs -f frontend
```

### 4. 停止服务

```bash
docker-compose down
```

### 6. 停止并删除数据卷（谨慎使用）

```bash
docker-compose down -v
```

## 单独构建和运行

### 后端服务

```bash
# 构建镜像
docker build -f Dockerfile.backend -t crypto-backend .

# 运行容器
docker run -d \
  --name crypto_backend \
  -p 8000:8000 \
  -v $(pwd)/db:/app/db \
  crypto-backend
```

### 前端服务

```bash
# 构建镜像
cd frontend
docker build -t crypto-frontend .

# 运行容器
docker run -d \
  --name crypto_frontend \
  -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://localhost:8000 \
  crypto-frontend
```

## 访问服务

- 前端: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 数据持久化

数据库文件存储在 `./db` 目录中，通过 Docker volume 挂载，确保数据不会丢失。

## 环境变量

### 后端

- `PYTHONUNBUFFERED=1`: 确保Python输出实时显示

### 前端

- `NEXT_PUBLIC_API_URL`: 后端API地址（默认: http://backend:8000）

## 故障排查

### 1. 端口冲突

如果端口被占用，可以修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "8001:8000"  # 将8000改为8001
```

### 2. 数据库权限问题

确保 `db` 目录有正确的权限：

```bash
chmod -R 755 db/
```

### 3. 查看容器日志

```bash
docker-compose logs backend
docker-compose logs frontend
```

### 4. 进入容器调试

```bash
# 进入后端容器
docker-compose exec backend bash

# 进入前端容器
docker-compose exec frontend sh
```

## 更新代码

修改代码后，需要重新构建镜像：

```bash
docker-compose up -d --build
```

## 生产环境建议

1. 使用环境变量文件（`.env`）管理敏感信息
2. 配置反向代理（如 Nginx）
3. 启用 HTTPS
4. 配置日志轮转
5. 设置资源限制（CPU、内存）

