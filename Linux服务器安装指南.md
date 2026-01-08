# Linux 服务器安装指南

本文档介绍如何在 Linux 服务器上安装和部署该项目。

## 目录

- [系统要求](#系统要求)
- [安装方式](#安装方式)
  - [方式一：Docker 部署（推荐）](#方式一docker-部署推荐)
  - [方式二：直接安装](#方式二直接安装)
- [配置说明](#配置说明)
- [启动服务](#启动服务)
- [验证安装](#验证安装)
- [生产环境配置](#生产环境配置)
- [故障排查](#故障排查)

---

## 系统要求

### 最低配置
- **操作系统**: Ubuntu 20.04+ / CentOS 7+ / Debian 10+ 或其他 Linux 发行版
- **CPU**: 2 核
- **内存**: 4GB RAM
- **磁盘**: 20GB 可用空间
- **网络**: 可访问互联网（用于下载数据和依赖）

### 推荐配置
- **CPU**: 4 核或更多
- **内存**: 8GB RAM 或更多
- **磁盘**: 50GB+ SSD（数据库和日志文件）
- **网络**: 稳定的网络连接

---

## 安装方式

### 方式一：Docker 部署（推荐）

Docker 部署方式简单、隔离性好，适合生产环境。

#### 1. 安装 Docker 和 Docker Compose

**Ubuntu/Debian:**

```bash
# 更新系统包
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

# 添加 Docker 仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 验证安装
docker --version
docker compose version
```

**CentOS/RHEL:**

```bash
# 安装必要的依赖
sudo yum install -y yum-utils

# 添加 Docker 仓库
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 安装 Docker Engine
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
docker --version
docker compose version
```

**配置 Docker 镜像加速（可选，国内服务器推荐）:**

参考 `Docker镜像加速配置.md` 文件配置镜像加速器。

#### 2. 克隆或上传项目代码

**方式1: 使用 Git 克隆（如果有 Git 仓库）**

```bash
git clone <your-repo-url> crypto-top2
cd crypto-top2
```

**方式2: 使用 SCP 上传（从本地）**

SCP 支持多种认证方式，选择适合你的方式：

**a) 使用密码认证（最简单）**

```bash
# 在本地执行，会提示输入密码
scp -r /path/to/top2 user@server:/opt/crypto-top2
```

**b) 使用 SSH 密钥文件（PEM 文件）**

```bash
# 如果服务器使用 PEM 密钥文件
scp -i /path/to/your-key.pem -r /path/to/top2 user@server:/opt/crypto-top2

# 示例：
scp -i ~/Downloads/my-server.pem -r ./top2 ubuntu@192.168.1.100:/opt/crypto-top2
```

**c) 使用默认 SSH 密钥（已配置 SSH）**

如果已经配置了 SSH 密钥（`~/.ssh/id_rsa` 等），可以直接使用：

```bash
# 直接上传，无需指定密钥
scp -r /path/to/top2 user@server:/opt/crypto-top2
```

**d) 使用 rsync（推荐，支持断点续传）**

```bash
# 使用密码
rsync -avz --progress /path/to/top2/ user@server:/opt/crypto-top2/

# 使用 PEM 密钥
rsync -avz --progress -e "ssh -i /path/to/your-key.pem" /path/to/top2/ user@server:/opt/crypto-top2/

# 使用默认 SSH 密钥
rsync -avz --progress /path/to/top2/ user@server:/opt/crypto-top2/
```

**e) 使用 tar + ssh（适合大文件）**

```bash
# 在本地打包
cd /path/to
tar czf top2.tar.gz top2/

# 上传压缩包
scp -i /path/to/your-key.pem top2.tar.gz user@server:/tmp/

# 在服务器上解压
ssh -i /path/to/your-key.pem user@server "cd /opt && sudo tar xzf /tmp/top2.tar.gz && sudo chown -R user:user /opt/top2"
```

**上传后，在服务器上：**

```bash
cd /opt/crypto-top2
```

#### 3. 创建必要的目录

```bash
# 创建数据库目录
mkdir -p db
mkdir -p backtrade_records

# 设置权限
chmod -R 755 db
chmod -R 755 backtrade_records
```

#### 4. 构建并启动服务

**使用标准配置:**

```bash
docker compose up -d --build
```

**使用国内镜像源配置:**

```bash
docker compose -f docker-compose.cn.yml up -d --build
```

#### 5. 查看服务状态

```bash
# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f

# 查看后端日志
docker compose logs -f backend

# 查看前端日志
docker compose logs -f frontend
```

---

### 方式二：直接安装

如果不想使用 Docker，可以直接在服务器上安装。

#### 1. 安装系统依赖

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nodejs \
    npm \
    sqlite3 \
    build-essential \
    gcc
```

**CentOS/RHEL:**

```bash
sudo yum install -y \
    python3.11 \
    python3-pip \
    nodejs \
    npm \
    sqlite \
    gcc \
    gcc-c++ \
    make
```

#### 2. 安装 Node.js（如果版本太低）

```bash
# 使用 NodeSource 安装 Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# 或使用 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18
```

#### 3. 设置项目目录

```bash
# 创建项目目录
sudo mkdir -p /opt/crypto-top2
sudo chown $USER:$USER /opt/crypto-top2
cd /opt/crypto-top2

# 上传或克隆项目代码
# ...
```

#### 4. 安装后端依赖

```bash
# 创建 Python 虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

#### 5. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

#### 6. 创建数据库目录

```bash
mkdir -p db
mkdir -p backtrade_records
```

#### 7. 配置环境变量（可选）

创建 `.env` 文件：

```bash
cat > .env << EOF
PYTHONUNBUFFERED=1
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
```

#### 8. 启动服务

**使用 systemd 服务（推荐）:**

创建后端服务文件 `/etc/systemd/system/crypto-backend.service`:

```ini
[Unit]
Description=Crypto Backend API Service
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/opt/crypto-top2
Environment="PATH=/opt/crypto-top2/venv/bin"
ExecStart=/opt/crypto-top2/venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

创建前端服务文件 `/etc/systemd/system/crypto-frontend.service`:

```ini
[Unit]
Description=Crypto Frontend Service
After=network.target crypto-backend.service

[Service]
Type=simple
User=your-username
WorkingDirectory=/opt/crypto-top2/frontend
Environment="NEXT_PUBLIC_API_URL=http://localhost:8000"
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:

```bash
# 先构建前端
cd frontend
npm run build
cd ..

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable crypto-backend crypto-frontend
sudo systemctl start crypto-backend crypto-frontend

# 查看状态
sudo systemctl status crypto-backend
sudo systemctl status crypto-frontend
```

**手动启动（开发/测试）:**

```bash
# 终端1: 启动后端
source venv/bin/activate
uvicorn api_server:app --host 0.0.0.0 --port 8000

# 终端2: 启动前端
cd frontend
npm run dev  # 开发模式
# 或
npm run build && npm start  # 生产模式
```

---

## 配置说明

### 端口配置

默认端口：
- **后端**: 8000
- **前端**: 3000

如需修改端口，编辑 `docker-compose.yml` 或 systemd 服务文件。

### 数据库配置

数据库文件存储在 `./db/crypto_data.db`，确保该目录有写权限。

### 防火墙配置

如果使用防火墙，需要开放相应端口：

```bash
# Ubuntu/Debian (UFW)
sudo ufw allow 8000/tcp
sudo ufw allow 3000/tcp
sudo ufw reload

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload

# 或使用 iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 3000 -j ACCEPT
```

---

## 启动服务

### Docker 方式

```bash
# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 重启服务
docker compose restart

# 查看日志
docker compose logs -f
```

### 直接安装方式

```bash
# 使用 systemd
sudo systemctl start crypto-backend crypto-frontend

# 停止
sudo systemctl stop crypto-backend crypto-frontend

# 重启
sudo systemctl restart crypto-backend crypto-frontend

# 查看日志
sudo journalctl -u crypto-backend -f
sudo journalctl -u crypto-frontend -f
```

---

## 验证安装

### 1. 检查服务状态

**Docker 方式:**

```bash
docker compose ps
```

**直接安装方式:**

```bash
sudo systemctl status crypto-backend crypto-frontend
```

### 2. 检查后端 API

```bash
# 健康检查
curl http://localhost:8000/api/health

# 应该返回:
# {"status":"healthy","timestamp":"..."}
```

### 3. 检查前端

在浏览器中访问 `http://your-server-ip:3000`，应该能看到前端界面。

### 4. 检查 API 文档

访问 `http://your-server-ip:8000/docs` 查看 Swagger API 文档。

---

## 生产环境配置

### 1. 使用 Nginx 反向代理（推荐）

安装 Nginx:

```bash
sudo apt-get install nginx  # Ubuntu/Debian
sudo yum install nginx       # CentOS/RHEL
```

创建 Nginx 配置 `/etc/nginx/sites-available/crypto-top2`:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 后端 API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置:

```bash
sudo ln -s /etc/nginx/sites-available/crypto-top2 /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 2. 配置 HTTPS（使用 Let's Encrypt）

```bash
# 安装 Certbot
sudo apt-get install certbot python3-certbot-nginx  # Ubuntu/Debian
sudo yum install certbot python3-certbot-nginx      # CentOS/RHEL

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 3. 配置日志轮转

创建日志轮转配置 `/etc/logrotate.d/crypto-top2`:

```
/opt/crypto-top2/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 your-username your-username
}
```

### 4. 设置资源限制

**Docker 方式:**

在 `docker-compose.yml` 中添加资源限制:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

**直接安装方式:**

编辑 systemd 服务文件，添加资源限制。

### 5. 监控和告警

建议配置监控工具（如 Prometheus + Grafana）来监控服务状态。

---

## 故障排查

### 问题1: 端口被占用

```bash
# 检查端口占用
sudo netstat -tulpn | grep :8000
sudo netstat -tulpn | grep :3000

# 或使用 ss
sudo ss -tulpn | grep :8000

# 杀死占用进程
sudo kill -9 <PID>
```

### 问题2: 权限问题

```bash
# 检查目录权限
ls -la db/
ls -la backtrade_records/

# 修复权限
chmod -R 755 db
chmod -R 755 backtrade_records
chown -R $USER:$USER db backtrade_records
```

### 问题3: Docker 容器无法启动

```bash
# 查看详细日志
docker compose logs backend
docker compose logs frontend

# 检查镜像
docker images

# 清理并重建
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 问题4: 数据库连接失败

```bash
# 检查数据库文件
ls -lh db/crypto_data.db

# 检查数据库权限
sqlite3 db/crypto_data.db "SELECT 1;"

# 重新初始化数据库（谨慎操作）
python3 init_db.py
```

### 问题5: 前端无法连接后端

```bash
# 检查后端是否运行
curl http://localhost:8000/api/health

# 检查前端环境变量
cd frontend
cat .env.local  # 或检查 NEXT_PUBLIC_API_URL

# 检查网络连接
ping localhost
```

### 问题6: 内存不足

```bash
# 检查内存使用
free -h

# 检查 Docker 资源使用
docker stats

# 清理未使用的 Docker 资源
docker system prune -a
```

### 获取详细错误信息

**Docker 方式:**

```bash
# 进入容器查看
docker compose exec backend bash
docker compose exec frontend sh

# 查看完整日志
docker compose logs --tail=100 backend
```

**直接安装方式:**

```bash
# 查看 systemd 日志
sudo journalctl -u crypto-backend -n 100
sudo journalctl -u crypto-frontend -n 100

# 查看系统日志
sudo dmesg | tail -50
```

---

## 快速参考命令

### Docker 方式

```bash
# 启动
docker compose up -d

# 停止
docker compose down

# 重启
docker compose restart

# 查看日志
docker compose logs -f

# 更新代码后重建
docker compose up -d --build

# 进入容器
docker compose exec backend bash
docker compose exec frontend sh
```

### 直接安装方式

```bash
# 启动服务
sudo systemctl start crypto-backend crypto-frontend

# 停止服务
sudo systemctl stop crypto-backend crypto-frontend

# 重启服务
sudo systemctl restart crypto-backend crypto-frontend

# 查看状态
sudo systemctl status crypto-backend crypto-frontend

# 查看日志
sudo journalctl -u crypto-backend -f
sudo journalctl -u crypto-frontend -f

# 启用开机自启
sudo systemctl enable crypto-backend crypto-frontend
```

---

## 下一步

安装完成后，建议：

1. **下载初始数据**: 使用 `download_klines.py` 下载历史 K 线数据
2. **配置数据完整性检查**: 运行数据完整性检查确保数据质量
3. **测试回测功能**: 在前端界面运行一次回测验证功能正常
4. **设置定期备份**: 配置数据库自动备份脚本
5. **配置监控**: 设置服务监控和告警

---

## 获取帮助

如果遇到问题：

1. 查看日志文件获取详细错误信息
2. 检查 `故障排查.md` 文档
3. 查看项目 GitHub Issues（如果有）
4. 联系项目维护者

---

**祝安装顺利！**

