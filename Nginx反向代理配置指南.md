# Nginx 反向代理配置指南

## 为什么需要 Nginx？

在生产环境部署时，使用 Nginx 做反向代理有以下优势：

✅ **统一端口** - 所有服务通过 80/443 端口访问  
✅ **HTTPS 支持** - 统一管理 SSL 证书  
✅ **隐藏后端端口** - 提高安全性  
✅ **静态文件服务** - 高效提供前端静态资源  
✅ **负载均衡** - 支持多实例部署  
✅ **安全配置** - 添加安全头、限流等  
✅ **日志管理** - 统一访问日志  

---

## 项目服务端口

- **前端 (Next.js)**: 3000
- **数据服务**: 8001
- **回测服务**: 8002
- **订单服务**: 8003

---

## 安装 Nginx

### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y nginx

# 启动 Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# 检查状态
sudo systemctl status nginx
```

### CentOS/RHEL

```bash
sudo yum install -y nginx
# 或 (CentOS 8+)
sudo dnf install -y nginx

sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## 基础配置

### 方案1: 单一域名配置（推荐）

所有服务通过一个域名访问，使用路径区分：

```
https://yourdomain.com/          → 前端
https://yourdomain.com/api/data/  → 数据服务 (8001)
https://yourdomain.com/api/backtest/ → 回测服务 (8002)
https://yourdomain.com/api/order/ → 订单服务 (8003)
```

**配置文件**: `/etc/nginx/sites-available/corniche`

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL 证书配置（使用 Let's Encrypt）
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 日志
    access_log /var/log/nginx/corniche_access.log;
    error_log /var/log/nginx/corniche_error.log;

    # 客户端最大请求体大小（用于文件上传）
    client_max_body_size 100M;

    # 前端 - Next.js
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 数据服务 API
    location /api/data/ {
        proxy_pass http://localhost:8001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS 头（如果需要）
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
        
        if ($request_method = OPTIONS) {
            return 204;
        }
        
        # 超时设置（数据下载可能需要较长时间）
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 回测服务 API
    location /api/backtest/ {
        proxy_pass http://localhost:8002/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置（回测可能需要较长时间）
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

    # 订单服务 API
    location /api/order/ {
        proxy_pass http://localhost:8003/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件缓存（Next.js 静态资源）
    location /_next/static/ {
        proxy_pass http://localhost:3000;
        proxy_cache_valid 200 60m;
        add_header Cache-Control "public, immutable";
    }
}
```

---

### 方案2: 子域名配置

使用不同子域名访问不同服务：

```
https://yourdomain.com          → 前端
https://api-data.yourdomain.com → 数据服务
https://api-backtest.yourdomain.com → 回测服务
https://api-order.yourdomain.com → 订单服务
```

**配置文件**: `/etc/nginx/sites-available/corniche`

```nginx
# 前端
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

# 数据服务
server {
    listen 443 ssl http2;
    server_name api-data.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api-data.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api-data.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}

# 回测服务
server {
    listen 443 ssl http2;
    server_name api-backtest.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api-backtest.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api-backtest.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}

# 订单服务
server {
    listen 443 ssl http2;
    server_name api-order.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api-order.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api-order.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8003;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 配置步骤

### 1. 创建配置文件

```bash
# 创建配置文件
sudo nano /etc/nginx/sites-available/corniche

# 将上面的配置内容粘贴进去，修改域名和路径
```

### 2. 启用配置

```bash
# 创建符号链接
sudo ln -s /etc/nginx/sites-available/corniche /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重新加载 Nginx
sudo systemctl reload nginx
```

### 3. 配置 SSL 证书（Let's Encrypt）

```bash
# 安装 Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# 获取证书（单一域名）
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# 如果使用子域名，需要为每个子域名获取证书
sudo certbot --nginx -d api-data.yourdomain.com
sudo certbot --nginx -d api-backtest.yourdomain.com
sudo certbot --nginx -d api-order.yourdomain.com

# 自动续期测试
sudo certbot renew --dry-run
```

---

## 更新前端环境变量

如果使用路径代理（方案1），需要更新前端环境变量：

**`.env.production`**:

```bash
NEXT_PUBLIC_DATA_SERVICE_URL=https://yourdomain.com/api/data
NEXT_PUBLIC_BACKTEST_SERVICE_URL=https://yourdomain.com/api/backtest
NEXT_PUBLIC_ORDER_SERVICE_URL=https://yourdomain.com/api/order
```

**或更新 `lib/api-config.ts`**:

```typescript
export const API_URLS = {
  data: process.env.NEXT_PUBLIC_DATA_SERVICE_URL || 'https://yourdomain.com/api/data',
  backtest: process.env.NEXT_PUBLIC_BACKTEST_SERVICE_URL || 'https://yourdomain.com/api/backtest',
  order: process.env.NEXT_PUBLIC_ORDER_SERVICE_URL || 'https://yourdomain.com/api/order',
}
```

---

## Docker 环境配置

如果使用 Docker，需要修改配置：

```nginx
# Docker 容器名称
location /api/data/ {
    proxy_pass http://data-service:8001/;
    # ...
}

location /api/backtest/ {
    proxy_pass http://backtest-service:8002/;
    # ...
}

location /api/order/ {
    proxy_pass http://order-service:8003/;
    # ...
}

location / {
    proxy_pass http://frontend:3000;
    # ...
}
```

**Docker Compose 中添加 Nginx**:

```yaml
nginx:
  image: nginx:alpine
  container_name: nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf
    - ./nginx/sites:/etc/nginx/conf.d
    - ./nginx/ssl:/etc/nginx/ssl
  depends_on:
    - frontend
    - data-service
    - backtest-service
    - order-service
  restart: unless-stopped
  networks:
    - crypto-network
```

---

## 安全配置

### 1. 限制访问频率

```nginx
# 在 http 块中添加
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# 在 location 中使用
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    # ...
}
```

### 2. 隐藏 Nginx 版本

```nginx
server_tokens off;
```

### 3. 禁止访问隐藏文件

```nginx
location ~ /\. {
    deny all;
    access_log off;
    log_not_found off;
}
```

---

## 性能优化

### 1. 启用 Gzip 压缩

```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;
```

### 2. 静态文件缓存

```nginx
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### 3. 连接池

```nginx
upstream backend_pool {
    server localhost:8001;
    server localhost:8002;
    server localhost:8003;
    keepalive 32;
}
```

---

## 监控和日志

### 查看访问日志

```bash
# 实时查看
sudo tail -f /var/log/nginx/corniche_access.log

# 查看错误日志
sudo tail -f /var/log/nginx/corniche_error.log

# 统计访问量
sudo awk '{print $1}' /var/log/nginx/corniche_access.log | sort | uniq -c | sort -rn | head -10
```

---

## 常见问题

### Q1: 502 Bad Gateway

**原因**: 后端服务未启动或无法连接

**解决方法**:
```bash
# 检查后端服务是否运行
curl http://localhost:8001
curl http://localhost:8002
curl http://localhost:8003

# 检查 Nginx 错误日志
sudo tail -f /var/log/nginx/error.log
```

### Q2: 504 Gateway Timeout

**原因**: 请求超时

**解决方法**:
```nginx
# 增加超时时间
proxy_connect_timeout 600s;
proxy_send_timeout 600s;
proxy_read_timeout 600s;
```

### Q3: CORS 错误

**解决方法**:
```nginx
# 在 location 块中添加 CORS 头
add_header Access-Control-Allow-Origin * always;
add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
```

---

## 完整配置示例

创建 `nginx-corniche.conf`:

```nginx
# /etc/nginx/sites-available/corniche

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS 主配置
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL 配置
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 日志
    access_log /var/log/nginx/corniche_access.log;
    error_log /var/log/nginx/corniche_error.log;

    # 客户端最大请求体
    client_max_body_size 100M;

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 数据服务
    location /api/data/ {
        proxy_pass http://localhost:8001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 回测服务
    location /api/backtest/ {
        proxy_pass http://localhost:8002/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

    # 订单服务
    location /api/order/ {
        proxy_pass http://localhost:8003/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 总结

✅ **推荐使用 Nginx** - 生产环境必备  
✅ **使用 HTTPS** - 保护数据传输  
✅ **统一端口** - 简化访问  
✅ **隐藏后端** - 提高安全性  
✅ **性能优化** - 压缩和缓存  

**快速部署步骤：**

1. 安装 Nginx
2. 创建配置文件
3. 配置 SSL 证书
4. 更新前端环境变量
5. 测试和重启服务
