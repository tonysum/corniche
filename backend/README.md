# 微服务架构

本项目已拆分为三个独立的微服务：

## 服务列表

### 1. 数据管理服务 (Data Service)
- **端口**: 8001
- **启动**: `python services/data_service/main.py`
- **职责**:
  - K线数据下载和管理
  - 数据查询和检索
  - 数据完整性检查
  - 数据修复和重检

### 2. 回测服务 (Backtest Service)
- **端口**: 8002
- **启动**: `python services/backtest_service/main.py`
- **职责**:
  - 交易策略回测
  - 回测结果计算和统计
  - 回测历史记录管理

### 3. 订单服务 (Order Service)
- **端口**: 8003
- **启动**: `python services/order_service/main.py`
- **职责**:
  - 订单价格计算
  - 建仓价格、止损价格、止盈价格计算

## 启动所有服务

### 方式1：使用启动脚本
```bash
./start-services.sh
```

### 方式2：手动启动
```bash
# 终端1：启动数据管理服务
python services/data_service/main.py

# 终端2：启动回测服务
python services/backtest_service/main.py

# 终端3：启动订单服务
python services/order_service/main.py
```

### 方式3：使用Docker Compose
```bash
docker-compose -f docker-compose.services.yml up
```

## API文档

启动服务后，访问以下地址查看API文档：

- **数据管理服务**: http://localhost:8001/docs
- **回测服务**: http://localhost:8002/docs
- **订单服务**: http://localhost:8003/docs

## 服务间通信

服务之间通过HTTP REST API进行通信。前端需要调用不同服务的不同端口。

## 共享资源

- **数据库**: 所有服务共享同一个SQLite数据库 (`db/crypto_data.db`)
- **共享模块**: `services/shared/` 目录包含共享的配置和工具函数
