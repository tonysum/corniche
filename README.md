# Corniche 项目

币安K线数据管理和交易回测系统

## 项目结构

```
corniche/
├── backend/          # 后端服务代码
│   ├── services/     # 微服务
│   │   ├── data_service/
│   │   ├── backtest_service/
│   │   └── order_service/
│   ├── *.py         # Python脚本文件
│   └── ...
├── frontend/         # 前端代码（Next.js）
│   ├── app/
│   ├── components/
│   └── ...
└── data/            # 数据文件
    ├── crypto_data.db
    ├── backtrade_records/
    └── *.csv
```

## 快速开始

### 使用 Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 本地开发

#### 后端

```bash
cd backend
pip install -r requirements.txt

# 启动数据服务
python services/data_service/main.py

# 启动回测服务
python services/backtest_service/main.py

# 启动订单服务
python services/order_service/main.py
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

## 服务端口

- 数据服务: 8001
- 回测服务: 8002
- 订单服务: 8003
- 前端: 3000

## 数据库

数据库文件位于 `data/crypto_data.db`，通过 Docker volume 挂载到容器中。

## 文档

更多详细信息请参考项目根目录下的各个 `.md` 文档文件。

