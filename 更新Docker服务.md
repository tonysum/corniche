# Docker 服务更新指南

## 程序更新后的 Docker 更新流程

### 方法一：完整重建（推荐，确保完全更新）

```bash
# 1. 停止并删除现有容器
docker-compose down

# 2. 重新构建镜像并启动（包含最新代码）
docker-compose up -d --build

# 3. 查看服务状态
docker-compose ps

# 4. 查看日志确认启动成功
docker-compose logs -f
```

### 方法二：仅重建特定服务

如果只更新了后端代码：

```bash
# 只重建并重启后端服务
docker-compose up -d --build backend

# 查看后端日志
docker-compose logs -f backend
```

如果只更新了前端代码：

```bash
# 只重建并重启前端服务
docker-compose up -d --build frontend

# 查看前端日志
docker-compose logs -f frontend
```

### 方法三：使用国内镜像源（如果使用 docker-compose.cn.yml）

```bash
# 停止现有容器
docker-compose -f docker-compose.cn.yml down

# 重新构建并启动
docker-compose -f docker-compose.cn.yml up -d --build

# 查看状态
docker-compose -f docker-compose.cn.yml ps
```

## 更新检查清单

### 1. 代码更新确认
- [ ] 确认代码已提交到仓库或本地已保存
- [ ] 检查 `requirements.txt` 是否更新（如果有新依赖）
- [ ] 检查 `package.json` 是否更新（前端）

### 2. 配置文件检查
- [ ] `docker-compose.yml` 配置是否需要调整
- [ ] 环境变量是否需要更新
- [ ] 端口映射是否需要修改

### 3. 数据备份（重要！）
```bash
# 备份数据库
cp -r db/crypto_data.db db/crypto_data.db.backup.$(date +%Y%m%d_%H%M%S)

# 备份回测记录
cp -r backtrade_records backtrade_records.backup.$(date +%Y%m%d_%H%M%S)
```

### 4. 更新后验证
```bash
# 检查容器状态
docker-compose ps

# 检查后端健康状态
curl http://localhost:8000/api/health

# 检查前端是否正常访问
curl http://localhost:3000

# 查看日志是否有错误
docker-compose logs --tail=50 backend
docker-compose logs --tail=50 frontend
```

## 常见更新场景

### 场景1：仅更新 Python 代码（后端）

```bash
# 快速更新流程
docker-compose restart backend  # 如果代码已通过 volume 挂载
# 或者
docker-compose up -d --build backend  # 如果代码在镜像中
```

### 场景2：更新依赖包

```bash
# 1. 更新 requirements.txt
# 2. 重新构建后端
docker-compose up -d --build backend
```

### 场景3：更新前端代码

```bash
# 1. 更新前端代码
# 2. 重新构建前端
docker-compose up -d --build frontend
```

### 场景4：更新 Dockerfile

```bash
# 如果修改了 Dockerfile，必须重新构建
docker-compose down
docker-compose up -d --build
```

## 强制更新（清理缓存）

如果遇到更新不生效的问题，可以强制清理并重建：

```bash
# 停止并删除容器
docker-compose down

# 删除旧镜像（可选，释放空间）
docker-compose down --rmi all

# 清理构建缓存（可选）
docker builder prune

# 重新构建（不使用缓存）
docker-compose build --no-cache

# 启动服务
docker-compose up -d
```

## 零停机更新（生产环境）

对于生产环境，可以使用滚动更新策略：

```bash
# 1. 先启动新容器（使用不同名称）
docker-compose -f docker-compose.yml up -d --build --scale backend=2

# 2. 等待新容器健康检查通过
docker-compose ps

# 3. 停止旧容器
docker-compose stop backend
docker-compose rm -f backend

# 4. 恢复单实例
docker-compose up -d --scale backend=1
```

## 更新脚本（自动化）

可以创建更新脚本 `update-docker.sh`：

```bash
#!/bin/bash

echo "开始更新 Docker 服务..."

# 备份数据
echo "备份数据..."
cp -r db/crypto_data.db db/crypto_data.db.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# 停止现有容器
echo "停止现有容器..."
docker-compose down

# 重新构建并启动
echo "重新构建并启动..."
docker-compose up -d --build

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查服务状态
echo "检查服务状态..."
docker-compose ps

# 检查健康状态
echo "检查后端健康状态..."
curl -f http://localhost:8000/api/health && echo "✓ 后端服务正常" || echo "✗ 后端服务异常"

echo "更新完成！"
```

使用方式：
```bash
chmod +x update-docker.sh
./update-docker.sh
```

## 故障排查

### 问题1：更新后服务无法启动

```bash
# 查看详细日志
docker-compose logs backend
docker-compose logs frontend

# 检查端口是否被占用
lsof -i :8000
lsof -i :3000

# 检查容器状态
docker-compose ps
```

### 问题2：代码更新未生效

```bash
# 确认代码已复制到容器
docker-compose exec backend ls -la /app/*.py

# 强制重新构建（不使用缓存）
docker-compose build --no-cache backend
docker-compose up -d backend
```

### 问题3：依赖安装失败

```bash
# 进入容器检查
docker-compose exec backend bash
pip list
pip install -r requirements.txt
```

## 注意事项

1. **数据持久化**：数据库和回测记录通过 volume 挂载，更新不会丢失数据
2. **环境变量**：如果修改了环境变量，需要重启容器才能生效
3. **端口冲突**：确保端口 8000 和 3000 未被其他程序占用
4. **镜像大小**：定期清理未使用的镜像：`docker image prune -a`
5. **日志管理**：定期清理日志：`docker-compose logs --tail=0 -f` 或配置日志轮转

## 快速参考命令

```bash
# 更新所有服务
docker-compose up -d --build

# 更新后端
docker-compose up -d --build backend

# 更新前端
docker-compose up -d --build frontend

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务（不重建）
docker-compose restart

# 查看服务状态
docker-compose ps
```

