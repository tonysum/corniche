'use client'

import { useState } from 'react'
import Link from 'next/link'
import BacktestForm from '@/components/BacktestForm'
import OrderCalculator from '@/components/OrderCalculator'
import { TopGainersProvider } from '@/contexts/TopGainersContext'

export default function BacktradeDashboard() {
  const [activeTab, setActiveTab] = useState<'backtest' | 'order'>('backtest')

  return (
    <TopGainersProvider>
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
                回测交易 Dashboard
              </h1>
              <p className="text-gray-400">策略回测和合约交易工具</p>
            </div>
            <Link 
              href="/data-dashboard"
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors text-sm"
            >
              ← 切换到数据 Dashboard
            </Link>
          </div>
        </header>

        {/* 标签页导航 */}
        <div className="flex space-x-4 mb-6 border-b border-gray-700">
          <button
            onClick={() => setActiveTab('backtest')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'backtest'
                ? 'text-purple-400 border-b-2 border-purple-400'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            回测交易
          </button>
          <button
            onClick={() => setActiveTab('order')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'order'
                ? 'text-pink-400 border-b-2 border-pink-400'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            合约下单
          </button>
        </div>

        {/* 内容区域 */}
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg shadow-xl p-6">
          {activeTab === 'backtest' && <BacktestForm />}
          {activeTab === 'order' && <OrderCalculator />}
        </div>
      </div>
    </main>
    </TopGainersProvider>
  )
}
