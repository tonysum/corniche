'use client'

interface SidebarProps {
  activeMenu: string
  onMenuChange: (menu: string) => void
}

export default function Sidebar({ activeMenu, onMenuChange }: SidebarProps) {
  const menuItems = [
    { id: 'download', label: '数据下载服务', icon: '📥' },
    { id: 'order', label: '合约下单', icon: '📊' },
    { id: 'backtest', label: '回测交易', icon: '📈' },
    { id: 'integrity', label: '数据完整性检查', icon: '🔍' },
  ]

  return (
    <div className="w-64 bg-gray-800/80 backdrop-blur-sm border-r border-gray-700 min-h-screen p-4">
      <div className="mb-8">
        <h2 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-600 bg-clip-text text-transparent">
          币安交易工具
        </h2>
        <p className="text-gray-400 text-sm mt-1">管理和交易服务</p>
      </div>

      <nav className="space-y-2">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onMenuChange(item.id)}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all ${
              activeMenu === item.id
                ? 'bg-blue-600 text-white shadow-lg'
                : 'text-gray-300 hover:bg-gray-700 hover:text-white'
            }`}
          >
            <span className="text-xl">{item.icon}</span>
            <span className="font-medium">{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}

