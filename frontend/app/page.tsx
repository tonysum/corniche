'use client'

import { useState } from 'react'
import Sidebar from '@/components/Sidebar'
import DownloadForm from '@/components/DownloadForm'
import DeleteForm from '@/components/DeleteForm'
import EditDataForm from '@/components/EditDataForm'
import KlineViewer from '@/components/KlineViewer'
import SymbolListWithChart from '@/components/SymbolListWithChart'
import OrderCalculator from '@/components/OrderCalculator'
import BacktestForm from '@/components/BacktestForm'
import DataIntegrityChecker from '@/components/DataIntegrityChecker'
import { TopGainersProvider } from '@/contexts/TopGainersContext'

export default function Home() {
  const [activeMenu, setActiveMenu] = useState('download')
  const [activeTab, setActiveTab] = useState<'download' | 'delete' | 'edit' | 'kline' | 'list-chart'>('download')

  return (
    <TopGainersProvider>
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white flex">
      {/* 左侧菜单栏 */}
      <Sidebar activeMenu={activeMenu} onMenuChange={setActiveMenu} />

      {/* 主内容区域 */}
      <div className="flex-1 overflow-auto">
        <div className="container mx-auto px-4 py-8">
          {activeMenu === 'download' && (
            <>
              <header className="mb-8">
                <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-600 bg-clip-text text-transparent">
                  币安K线数据下载服务
                </h1>
                <p className="text-gray-400">管理和下载币安U本位合约K线数据</p>
              </header>

              {/* 标签页导航 */}
              <div className="flex space-x-4 mb-6 border-b border-gray-700">
                <button
                  onClick={() => setActiveTab('download')}
                  className={`px-6 py-3 font-medium transition-colors ${
                    activeTab === 'download'
                      ? 'text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                >
                  下载数据
                </button>
                <button
                  onClick={() => setActiveTab('delete')}
                  className={`px-6 py-3 font-medium transition-colors ${
                    activeTab === 'delete'
                      ? 'text-red-400 border-b-2 border-red-400'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                >
                  删除数据
                </button>
                <button
                  onClick={() => setActiveTab('edit')}
                  className={`px-6 py-3 font-medium transition-colors ${
                    activeTab === 'edit'
                      ? 'text-yellow-400 border-b-2 border-yellow-400'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                >
                  修改数据
                </button>
                <button
                  onClick={() => setActiveTab('kline')}
                  className={`px-6 py-3 font-medium transition-colors ${
                    activeTab === 'kline'
                      ? 'text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                >
                  查看K线
                </button>
                <button
                  onClick={() => setActiveTab('list-chart')}
                  className={`px-6 py-3 font-medium transition-colors ${
                    activeTab === 'list-chart'
                      ? 'text-blue-400 border-b-2 border-blue-400'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                >
                  列表与图表
                </button>
              </div>

              {/* 内容区域 */}
              <div 
                className={`bg-gray-800/50 backdrop-blur-sm rounded-lg shadow-xl ${
                  activeTab === 'list-chart' ? 'p-4' : 'p-6'
                }`}
                style={activeTab === 'list-chart' ? { height: 'calc(100vh - 250px)', minHeight: '600px' } : {}}
              >
                {activeTab === 'download' && <DownloadForm />}
                {activeTab === 'delete' && <DeleteForm />}
                {activeTab === 'edit' && <EditDataForm />}
                {activeTab === 'kline' && <KlineViewer />}
                {activeTab === 'list-chart' && <SymbolListWithChart />}
              </div>
            </>
          )}

          {activeMenu === 'order' && (
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 shadow-xl">
              <OrderCalculator />
            </div>
          )}

          {activeMenu === 'backtest' && (
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 shadow-xl">
              <BacktestForm />
            </div>
          )}

          {activeMenu === 'integrity' && (
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 shadow-xl">
              <DataIntegrityChecker />
            </div>
          )}
        </div>
      </div>
    </main>
    </TopGainersProvider>
  )
}
