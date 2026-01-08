# 币安K线数据下载前端

使用 Next.js 构建的前端界面，用于管理和下载币安U本位合约K线数据。

## 功能特性

- 📥 **下载K线数据** - 支持下载指定交易对或所有交易对的K线数据
- 📊 **交易对列表** - 查看本地数据库中已存在的交易对
- 📈 **K线数据查看** - 查询和查看指定交易对的K线数据
- 🎨 **现代化UI** - 使用 Tailwind CSS 构建的响应式界面

## 安装和运行

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

复制 `.env.local.example` 为 `.env.local` 并修改后端API地址（如果需要）：

```bash
cp .env.local.example .env.local
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000 查看应用。

### 4. 构建生产版本

```bash
npm run build
npm start
```

## 使用说明

### 下载K线数据

1. 在"下载数据"标签页中：
   - 选择K线间隔（如：1天、1小时等）
   - 可选：输入交易对符号（如：BTCUSDT），留空则下载所有交易对
   - 可选：设置开始时间和结束时间
   - 可选：设置回溯天数
   - 点击"开始下载"按钮

### 查看交易对列表

1. 在"交易对列表"标签页中：
   - 选择K线间隔
   - 查看本地数据库中已存在的所有交易对
   - 点击"刷新"按钮更新列表

### 查看K线数据

1. 在"查看K线"标签页中：
   - 选择K线间隔
   - 输入交易对符号
   - 可选：设置开始日期和结束日期
   - 点击"查询数据"按钮

## 技术栈

- **Next.js 16** - React框架
- **TypeScript** - 类型安全
- **Tailwind CSS** - 样式框架
- **React Hooks** - 状态管理

## 后端API要求

前端需要连接到运行在 `http://localhost:8000` 的 FastAPI 后端服务器。

确保后端服务已启动：
```bash
cd ..
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

## 项目结构

```
frontend/
├── app/
│   ├── page.tsx          # 主页面
│   ├── layout.tsx        # 布局组件
│   └── globals.css       # 全局样式
├── components/
│   ├── DownloadForm.tsx  # 下载表单组件
│   ├── SymbolList.tsx    # 交易对列表组件
│   └── KlineViewer.tsx   # K线查看器组件
└── package.json
```
