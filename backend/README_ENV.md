# 环境变量配置说明

## 📋 概述

项目已改为使用 `.env` 文件存储敏感配置信息（如 API 密钥），避免将敏感信息硬编码在代码中。

## 🔧 配置步骤

### 1. 安装依赖

确保已安装 `python-dotenv`：

```bash
pip install python-dotenv
```

或使用 requirements.txt：

```bash
pip install -r requirements.txt
```

### 2. 创建 .env 文件

在项目根目录（`/Users/tony/Documents/crypto/corniche/`）创建 `.env` 文件：

```bash
cp .env.example .env
```

### 3. 编辑 .env 文件

打开 `.env` 文件，填入你的币安 API 密钥：

```env
# 币安API密钥（必填）
BINANCE_API_KEY=your_actual_api_key_here
BINANCE_API_SECRET=your_actual_api_secret_here

# API基础路径（可选，默认使用生产环境URL）
# BASE_PATH=https://fapi.binance.com

# 数据库路径（可选，默认使用项目根目录下的 data/crypto_data.db）
# DB_PATH=/path/to/your/database.db
```

## 🔒 安全说明

- ✅ `.env` 文件已添加到 `.gitignore`，不会被提交到版本控制
- ✅ 不要将 `.env` 文件分享给他人或上传到公共仓库
- ✅ 如果 API 密钥泄露，请立即在币安后台重新生成

## 📝 配置优先级

配置的优先级顺序（从高到低）：

1. **函数参数**：如果调用时传入了 `api_key` 或 `api_secret` 参数
2. **环境变量**：系统环境变量 `BINANCE_API_KEY` 和 `BINANCE_API_SECRET`
3. **.env 文件**：项目根目录或 backend 目录下的 `.env` 文件
4. **默认值**：如果以上都未设置，会抛出错误（不再使用硬编码的默认值）

## 🔍 .env 文件查找路径

代码会按以下顺序查找 `.env` 文件：

1. 项目根目录：`/Users/tony/Documents/crypto/corniche/.env`
2. backend 目录：`/Users/tony/Documents/crypto/corniche/backend/.env`

如果找到 `.env` 文件，会输出日志：
```
已加载环境变量文件: /path/to/.env
```

如果未找到，会输出警告：
```
未找到 .env 文件，将使用环境变量或默认值。查找路径: /path/to/.env
```

## ⚠️ 错误处理

如果未设置 `BINANCE_API_KEY` 或 `BINANCE_API_SECRET`，程序会抛出清晰的错误信息：

```
ValueError: BINANCE_API_KEY 未设置。请创建 .env 文件并设置 BINANCE_API_KEY，或在环境变量中设置 BINANCE_API_KEY。
```

## 📚 相关文件

- `.env.example`：环境变量模板文件（可提交到版本控制）
- `.env`：实际配置文件（**不要**提交到版本控制）
- `binance_api.py`：加载和使用环境变量的代码

## 🚀 使用示例

### 方式1：使用 .env 文件（推荐）

1. 创建 `.env` 文件并填入 API 密钥
2. 直接运行代码，会自动加载 `.env` 文件：

```python
from binance_api import BinanceAPI

# 会自动从 .env 文件加载配置
api = BinanceAPI()
```

### 方式2：使用环境变量

```bash
export BINANCE_API_KEY=your_api_key
export BINANCE_API_SECRET=your_api_secret
python your_script.py
```

### 方式3：代码中直接传入（不推荐，仅用于测试）

```python
from binance_api import BinanceAPI

api = BinanceAPI(
    api_key="your_api_key",
    api_secret="your_api_secret"
)
```
