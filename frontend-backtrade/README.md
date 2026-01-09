# 回测交易前端

币安交易策略回测和合约交易前端应用。

## 功能特性

- 📈 **标准回测** - 配置化参数的回测策略
- 🧠 **聪明钱回测** - 基于聪明钱策略的回测
- 💰 **合约下单** - 合约订单计算工具

## 安装和运行

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

创建 `.env.local` 文件：

```bash
NEXT_PUBLIC_DATA_SERVICE_URL=http://localhost:8001
NEXT_PUBLIC_BACKTEST_SERVICE_URL=http://localhost:8002
NEXT_PUBLIC_ORDER_SERVICE_URL=http://localhost:8003
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3002 查看应用。

### 4. 构建生产版本

```bash
npm run build
npm start
```

## 技术栈

- **Next.js 16** - React框架
- **TypeScript** - 类型安全
- **Tailwind CSS** - 样式框架
- **React Hooks** - 状态管理

## 端口

- **开发环境**: 3002
- **生产环境**: 3002

## 后端API要求

前端需要连接到以下后端服务：
- 数据服务: `http://localhost:8001`
- 回测服务: `http://localhost:8002`
- 订单服务: `http://localhost:8003`

确保后端服务已启动：
```bash
cd ../backend
python services/backtest_service/main.py
python services/order_service/main.py
```

## Docker 部署

```bash
# 构建镜像
docker build -t frontend-backtrade .

# 运行容器
docker run -p 3002:3002 frontend-backtrade
```

## 项目结构

```
frontend-backtrade/
├── app/
│   ├── page.tsx          # 主页面
│   ├── layout.tsx        # 布局组件
│   └── globals.css       # 全局样式
├── components/           # React 组件
├── lib/                  # 工具函数和配置
├── contexts/             # React Context
└── public/               # 静态资源
```
