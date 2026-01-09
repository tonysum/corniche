# Dashboard 结构说明

## 概述

前端应用已拆分为两个独立的 Dashboard：

1. **数据管理 Dashboard** (`/data-dashboard`) - 数据服务相关功能
2. **回测交易 Dashboard** (`/backtrade-dashboard`) - 回测和交易相关功能

---

## 路由结构

```
/
├── / (首页 - 选择 Dashboard)
├── /data-dashboard (数据管理 Dashboard)
└── /backtrade-dashboard (回测交易 Dashboard)
```

---

## 数据管理 Dashboard (`/data-dashboard`)

### 功能模块

1. **下载数据** (`download`)
   - 组件: `DownloadForm`
   - 功能: 下载币安K线数据

2. **删除数据** (`delete`)
   - 组件: `DeleteForm`
   - 功能: 删除本地K线数据

3. **修改数据** (`edit`)
   - 组件: `EditDataForm`
   - 功能: 编辑本地K线数据

4. **查看K线** (`kline`)
   - 组件: `KlineViewer`
   - 功能: 查看和对比本地与币安API的K线数据

5. **列表与图表** (`list-chart`)
   - 组件: `SymbolListWithChart`
   - 功能: 交易对列表和图表展示

6. **完整性检查** (`integrity`)
   - 组件: `DataIntegrityChecker`
   - 功能: 数据完整性校验

### 文件位置

- `/frontend/app/data-dashboard/page.tsx`

---

## 回测交易 Dashboard (`/backtrade-dashboard`)

### 功能模块

1. **回测交易** (`backtest`)
   - 组件: `BacktestForm`
   - 功能: 
     - 标准回测
     - 聪明钱回测

2. **合约下单** (`order`)
   - 组件: `OrderCalculator`
   - 功能: 合约订单计算

### 文件位置

- `/frontend/app/backtrade-dashboard/page.tsx`

---

## 首页 (`/`)

首页提供两个 Dashboard 的选择入口，用户可以：
- 点击卡片进入对应的 Dashboard
- 查看每个 Dashboard 的功能说明

### 文件位置

- `/frontend/app/page.tsx`

---

## 组件结构

所有组件保持不变，位于：
- `/frontend/components/`

### 数据管理相关组件

- `DownloadForm.tsx`
- `DeleteForm.tsx`
- `EditDataForm.tsx`
- `KlineViewer.tsx`
- `SymbolListWithChart.tsx`
- `DataIntegrityChecker.tsx`

### 回测交易相关组件

- `BacktestForm.tsx`
- `OrderCalculator.tsx`

### 共享组件

- `Sidebar.tsx` (已不再使用，但保留)
- `KlineChart.tsx`
- `SymbolList.tsx`

---

## 导航

### Dashboard 间切换

每个 Dashboard 页面顶部都有导航按钮：
- 数据 Dashboard → "切换到回测 Dashboard"
- 回测 Dashboard → "切换到数据 Dashboard"

### 首页导航

首页提供两个 Dashboard 的入口卡片。

---

## 样式和主题

### 数据管理 Dashboard

- 主色调: 蓝色到紫色渐变 (`from-blue-400 to-purple-600`)
- 标签页颜色: 蓝色、红色、黄色、绿色

### 回测交易 Dashboard

- 主色调: 紫色到粉色渐变 (`from-purple-400 to-pink-600`)
- 标签页颜色: 紫色、粉色

---

## 使用方式

### 开发环境

```bash
cd frontend
npm run dev
```

访问：
- 首页: http://localhost:3000
- 数据 Dashboard: http://localhost:3000/data-dashboard
- 回测 Dashboard: http://localhost:3000/backtrade-dashboard

### 生产环境

构建后，路由会自动处理，无需额外配置。

---

## 迁移说明

### 从旧结构迁移

旧的结构使用侧边栏菜单 (`Sidebar`) 和单一页面 (`page.tsx`)，现在已改为：

1. **首页** - 选择 Dashboard
2. **数据 Dashboard** - 包含所有数据管理功能
3. **回测 Dashboard** - 包含所有回测和交易功能

### 旧路由映射

| 旧菜单 | 新位置 |
|--------|--------|
| 数据下载服务 | `/data-dashboard` → 下载数据标签 |
| 数据完整性检查 | `/data-dashboard` → 完整性检查标签 |
| 回测交易 | `/backtrade-dashboard` → 回测交易标签 |
| 合约下单 | `/backtrade-dashboard` → 合约下单标签 |

---

## 技术细节

### 路由

使用 Next.js App Router：
- `app/page.tsx` - 首页
- `app/data-dashboard/page.tsx` - 数据 Dashboard
- `app/backtrade-dashboard/page.tsx` - 回测 Dashboard

### 状态管理

- 每个 Dashboard 使用独立的 `useState` 管理标签页状态
- `TopGainersProvider` 仅在数据 Dashboard 中使用（因为只有数据相关组件需要）

### 样式

- 使用 Tailwind CSS
- 响应式设计，支持移动端
- 深色主题，渐变效果

---

## 后续优化建议

1. **添加面包屑导航** - 显示当前位置
2. **添加快捷键** - 快速切换 Dashboard
3. **保存用户偏好** - 记住上次访问的 Dashboard 和标签页
4. **添加搜索功能** - 快速查找功能
5. **移动端优化** - 优化移动端体验

---

## 总结

✅ **已完成：**
- 创建两个独立的 Dashboard
- 功能正确分离
- 添加导航链接
- 更新首页

✅ **优势：**
- 功能清晰分离
- 更好的用户体验
- 易于维护和扩展
- 符合单一职责原则
