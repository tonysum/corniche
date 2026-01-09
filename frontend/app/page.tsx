'use client'

import Link from 'next/link'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-blue-400 via-purple-500 to-pink-600 bg-clip-text text-transparent">
            币安交易工具平台
          </h1>
          <p className="text-gray-400 text-xl">管理和交易币安U本位合约数据</p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {/* 数据管理 Dashboard */}
          <Link href="/data-dashboard">
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg shadow-xl p-8 hover:bg-gray-800/70 transition-all cursor-pointer border border-gray-700 hover:border-blue-500">
              <div className="flex items-center mb-4">
                <span className="text-4xl mr-4">📊</span>
                <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-600 bg-clip-text text-transparent">
                  数据管理 Dashboard
                </h2>
              </div>
              <p className="text-gray-400 mb-6">
                管理和维护币安K线数据，包括下载、删除、修改、查看和完整性检查
              </p>
              <div className="flex flex-wrap gap-2">
                <span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm">下载数据</span>
                <span className="px-3 py-1 bg-red-500/20 text-red-300 rounded-full text-sm">删除数据</span>
                <span className="px-3 py-1 bg-yellow-500/20 text-yellow-300 rounded-full text-sm">修改数据</span>
                <span className="px-3 py-1 bg-green-500/20 text-green-300 rounded-full text-sm">完整性检查</span>
                <span className="px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full text-sm">查看K线</span>
              </div>
            </div>
          </Link>

          {/* 回测交易 Dashboard */}
          <Link href="/backtrade-dashboard">
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg shadow-xl p-8 hover:bg-gray-800/70 transition-all cursor-pointer border border-gray-700 hover:border-purple-500">
              <div className="flex items-center mb-4">
                <span className="text-4xl mr-4">📈</span>
                <h2 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
                  回测交易 Dashboard
                </h2>
              </div>
              <p className="text-gray-400 mb-6">
                策略回测和合约交易工具，包括标准回测、聪明钱回测和订单计算
              </p>
              <div className="flex flex-wrap gap-2">
                <span className="px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full text-sm">标准回测</span>
                <span className="px-3 py-1 bg-pink-500/20 text-pink-300 rounded-full text-sm">聪明钱回测</span>
                <span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm">合约下单</span>
              </div>
            </div>
          </Link>
        </div>

        <div className="text-center mt-12">
          <p className="text-gray-500 text-sm">
            选择上方的 Dashboard 开始使用
          </p>
        </div>
      </div>
    </main>
  )
}
