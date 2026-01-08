# K线数据下载服务端 API 文档

## 安装依赖

```bash
pip install fastapi uvicorn
```

## 启动服务

```bash
# 方式1：使用 uvicorn 命令
uvicorn api_server:app --host 0.0.0.0 --port 8000

# 方式2：直接运行 Python 文件
python api_server.py
```

## API 文档

启动服务后，访问以下地址查看交互式API文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API 端点

### 1. 根路径
- **GET** `/`
- 返回API信息和可用端点列表

### 2. 下载K线数据
- **POST** `/api/download`
- 请求体示例：
```json
{
  "interval": "1d",
  "symbol": "BTCUSDT",
  "start_time": "2025-01-01",
  "end_time": "2025-12-31",
  "limit": 1500,
  "update_existing": false,
  "missing_only": false
}
```

### 3. 查询本地交易对列表
- **GET** `/api/symbols?interval=1d`
- 返回指定时间间隔的所有交易对

### 4. 查询交易对的数据日期
- **GET** `/api/dates/{interval}/{symbol}`
- 示例：`/api/dates/1d/BTCUSDT`

### 5. 获取K线数据
- **GET** `/api/kline/{interval}/{symbol}?start_date=2025-01-01&end_date=2025-12-31`
- 示例：`/api/kline/1d/BTCUSDT?start_date=2025-01-01&end_date=2025-12-31`

### 6. 删除所有表
- **POST** `/api/tables/delete`
- 请求体：`{"confirm": true}`
- ⚠️ 警告：此操作不可逆！

### 7. 健康检查
- **GET** `/api/health`

## 使用示例

### 使用 curl

```bash
# 下载BTCUSDT的日线数据
curl -X POST "http://localhost:8000/api/download" \
  -H "Content-Type: application/json" \
  -d '{
    "interval": "1d",
    "symbol": "BTCUSDT",
    "start_time": "2025-01-01",
    "end_time": "2025-12-31"
  }'

# 查询本地所有日线交易对
curl "http://localhost:8000/api/symbols?interval=1d"

# 获取BTCUSDT的K线数据
curl "http://localhost:8000/api/kline/1d/BTCUSDT?start_date=2025-01-01&end_date=2025-12-31"
```

### 使用 Python requests

```python
import requests

# 下载K线数据
response = requests.post(
    "http://localhost:8000/api/download",
    json={
        "interval": "1d",
        "symbol": "BTCUSDT",
        "start_time": "2025-01-01",
        "end_time": "2025-12-31"
    }
)
print(response.json())

# 查询交易对列表
response = requests.get("http://localhost:8000/api/symbols?interval=1d")
print(response.json())
```
