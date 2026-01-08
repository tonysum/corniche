# 修复 lightningcss 错误指南

## 错误原因

`lightningcss` 是一个包含原生模块（.node 文件）的包，这些模块是平台特定的：
- macOS 上安装的是 `.darwin-x64.node`
- Windows 上安装的是 `.win32-x64.node`
- Linux 上需要的是 `.linux-x64-gnu.node`

如果你在 macOS/Windows 上安装了依赖，然后上传到 Linux 服务器，就会出现这个错误。

---

## 解决方案

### 方案1: 使用 Docker（推荐）

Docker 会在 Linux 容器内自动安装正确的依赖。

```bash
# 1. 停止现有容器
docker compose down

# 2. 清理旧的构建缓存
docker compose build --no-cache frontend

# 3. 重新构建并启动
docker compose up -d --build

# 4. 查看日志
docker compose logs -f frontend
```

---

### 方案2: 直接安装 - 在 Linux 服务器上重新安装依赖

如果你使用的是直接安装方式（非 Docker），需要在 Linux 服务器上重新安装 node_modules：

```bash
# 1. 进入前端目录
cd /root/beartshort/top2/frontend

# 2. 删除旧的 node_modules（可能包含错误的平台文件）
rm -rf node_modules package-lock.json .next

# 3. 清理 npm 缓存（可选）
npm cache clean --force

# 4. 重新安装依赖（在 Linux 服务器上）
npm install

# 5. 重新构建
npm run build

# 6. 启动服务
npm start
# 或开发模式
npm run dev
```

---

### 方案3: 使用 .dockerignore 和 .gitignore（最佳实践）

确保 `node_modules` 不会被上传到服务器：

**创建或更新 `.dockerignore`**:
```
node_modules
.next
.git
*.log
.env.local
```

**创建或更新 `.gitignore`**:
```
node_modules/
.next/
*.log
.env.local
```

然后：
1. 不要上传 `node_modules` 目录
2. 只上传源代码和 `package.json`
3. 在服务器上运行 `npm install`

---

### 方案4: 使用 rsync 排除 node_modules

如果必须上传文件，使用 rsync 排除 node_modules：

```bash
# 从本地上传（排除 node_modules）
rsync -avz --progress \
  --exclude 'node_modules' \
  --exclude '.next' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  ./top2/ user@server:/root/beartshort/top2/

# 然后在服务器上安装依赖
ssh user@server "cd /root/beartshort/top2/frontend && npm install"
```

---

## 详细步骤（直接安装方式）

### 步骤1: 清理旧文件

```bash
cd /root/beartshort/top2/frontend

# 删除所有可能包含错误平台文件的目录
rm -rf node_modules
rm -rf .next
rm -rf package-lock.json
```

### 步骤2: 重新安装依赖

```bash
# 确保在 Linux 服务器上
uname -a  # 应该显示 Linux

# 安装依赖
npm install

# 验证 lightningcss 是否正确安装
ls -la node_modules/lightningcss/lib/ | grep linux
# 应该看到 lightningcss.linux-x64-gnu.node 文件
```

### 步骤3: 验证安装

```bash
# 检查文件是否存在
find node_modules/lightningcss -name "*.node" -type f

# 应该看到类似：
# node_modules/lightningcss/lib/lightningcss.linux-x64-gnu.node
```

### 步骤4: 重新启动服务

```bash
# 开发模式
npm run dev

# 或生产模式
npm run build
npm start
```

---

## 如果使用 systemd 服务

如果使用 systemd 管理服务，需要重启：

```bash
# 重新安装依赖后
cd /root/beartshort/top2/frontend
npm install
npm run build

# 重启服务
sudo systemctl restart crypto-frontend

# 查看日志
sudo journalctl -u crypto-frontend -f
```

---

## 预防措施

### 1. 使用 Docker（最佳）

Docker 会自动处理平台差异，推荐使用。

### 2. 不要上传 node_modules

在 `.gitignore` 和 `.dockerignore` 中排除 `node_modules`：

```gitignore
node_modules/
.next/
*.log
.env.local
```

### 3. 使用 CI/CD

在 CI/CD 流程中，在目标平台上构建和安装依赖。

### 4. 使用多阶段构建（Docker）

确保在正确的平台上构建：

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install  # 在 Linux 容器内安装
COPY . .
RUN npm run build
```

---

## 验证修复

修复后，检查：

```bash
# 1. 检查 lightningcss 文件
ls -la node_modules/lightningcss/lib/lightningcss.linux-x64-gnu.node

# 2. 测试启动
cd frontend
npm run dev

# 3. 访问前端
curl http://localhost:3000

# 4. 检查日志（应该没有 lightningcss 错误）
# Docker 方式
docker compose logs frontend | grep -i lightningcss

# 直接安装方式
# 查看终端输出
```

---

## 常见问题

### Q1: npm install 很慢怎么办？

```bash
# 使用国内镜像源
npm config set registry https://registry.npmmirror.com

# 或使用 cnpm
npm install -g cnpm --registry=https://registry.npmmirror.com
cnpm install
```

### Q2: 还是报错怎么办？

```bash
# 完全清理
rm -rf node_modules package-lock.json .next
npm cache clean --force

# 重新安装
npm install

# 如果还有问题，检查 Node.js 版本
node --version  # 需要 Node.js 18+
```

### Q3: Docker 构建失败？

```bash
# 清理 Docker 缓存
docker system prune -a

# 重新构建（不使用缓存）
docker compose build --no-cache frontend
docker compose up -d
```

---

## 快速修复命令（一键执行）

**直接安装方式**:
```bash
cd /root/beartshort/top2/frontend && \
rm -rf node_modules .next package-lock.json && \
npm install && \
npm run build
```

**Docker 方式**:
```bash
docker compose down && \
docker compose build --no-cache frontend && \
docker compose up -d
```

---

**修复完成后，前端应该可以正常启动了！**

