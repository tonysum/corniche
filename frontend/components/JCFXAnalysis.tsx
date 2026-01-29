'use client'

import { useState, useEffect } from 'react'
import { API_URLS } from '../lib/api-config'

interface AnalysisResult {
  symbol: string
  pct_chg: number
  analysis_date: string
  entry_date: string
  analyze_open: number
  analyze_high: number
  analyze_low: number
  analyze_close: number
  risk_level: string
  should_delay: boolean
  premium_passed: boolean
  premium_reason?: string
  dynamic_params?: {
    leverage: number
    profit_threshold: number
    stop_loss_threshold: number
    add_position_threshold: number
  }
  delay_reasons?: string[]
}

export default function JCFXAnalysis() {
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const runAnalysis = async (targetDate?: string) => {
    setLoading(true)
    setError('')
    try {
      const url = new URL(`${API_URLS.backtest}/api/jcfx-analysis`) // Assuming it's on the backtest service
      if (targetDate) url.searchParams.append('date', targetDate)
      
      const response = await fetch(url.toString())
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '分析失败')
      }
      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '分析过程出错')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runAnalysis()
  }, [])

  const getRiskColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'low': return 'text-green-400 bg-green-400/10'
      case 'medium': return 'text-yellow-400 bg-yellow-400/10'
      case 'high': return 'text-red-400 bg-red-400/10'
      default: return 'text-gray-400 bg-gray-400/10'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
            漲幅第一做空分析
          </h2>
          <p className="text-gray-400">基于 UTC 0:00 开盘价统计 24h 涨幅并分析反向做空机会</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
          <button
            onClick={() => runAnalysis(date)}
            disabled={loading}
            className="px-6 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 rounded-lg font-medium transition-all shadow-lg shadow-purple-500/20"
          >
            {loading ? '分析中...' : '提交分析'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-900/30 border border-red-700 rounded-lg text-red-200 animate-pulse">
          ⚠️ {error}
        </div>
      )}

      {loading && !result && (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-gray-400 animate-pulse">正在扫描 PostgreSQL 数据库，计算全场涨幅...</p>
        </div>
      )}

      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {/* 核心信息卡片 */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-gray-800/40 backdrop-blur-md border border-purple-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4">
                <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${getRiskColor(result.risk_level)}`}>
                  {result.risk_level} Risk
                </span>
              </div>
              
              <div className="mb-6">
                <h3 className="text-4xl font-extrabold text-white mb-1">{result.symbol}</h3>
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <span>分析日期: {result.analysis_date}</span>
                  <span>•</span>
                  <span>建仓日期: {result.entry_date}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 bg-gray-900/50 rounded-xl">
                  <p className="text-xs text-gray-500 mb-1">24h 涨幅</p>
                  <p className="text-2xl font-bold text-green-400">+{result.pct_chg.toFixed(2)}%</p>
                </div>
                <div className="p-3 bg-gray-900/50 rounded-xl">
                  <p className="text-xs text-gray-500 mb-1">今日开盘</p>
                  <p className="text-xl font-mono text-gray-200">{result.analyze_open}</p>
                </div>
                <div className="p-3 bg-gray-900/50 rounded-xl">
                  <p className="text-xs text-gray-500 mb-1">今日最高</p>
                  <p className="text-xl font-mono text-gray-200">{result.analyze_high}</p>
                </div>
                <div className="p-3 bg-gray-900/50 rounded-xl">
                  <p className="text-xs text-gray-500 mb-1">当日收盘</p>
                  <p className="text-xl font-mono text-gray-200">{result.analyze_close}</p>
                </div>
              </div>
            </div>

            {/* 风控决策 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className={`p-6 rounded-2xl border ${result.premium_passed ? 'bg-green-900/10 border-green-500/30' : 'bg-red-900/10 border-red-500/30'}`}>
                <div className="flex items-center gap-3 mb-4">
                  <div className={`p-2 rounded-lg ${result.premium_passed ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    {result.premium_passed ? '✅' : '❌'}
                  </div>
                  <h4 className="font-bold text-lg">Premium 风控</h4>
                </div>
                <p className="text-sm text-gray-300">
                  {result.premium_passed 
                    ? 'Premium 指数处于安全区间，未触发拦截策略。'
                    : `Premium 风控拦截: ${result.premium_reason}`}
                </p>
              </div>

              <div className={`p-6 rounded-2xl border ${!result.should_delay ? 'bg-blue-900/10 border-blue-500/30' : 'bg-yellow-900/10 border-yellow-500/30'}`}>
                <div className="flex items-center gap-3 mb-4">
                  <div className={`p-2 rounded-lg ${!result.should_delay ? 'bg-blue-500/20 text-blue-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                    {!result.should_delay ? '🚀' : '⏳'}
                  </div>
                  <h4 className="font-bold text-lg">建仓建议</h4>
                </div>
                <p className="text-sm text-gray-300">
                  {!result.should_delay 
                    ? '多维度分析正常，建议开盘立即建仓做空。'
                    : '检测到潜在抛压不足或市场情绪过热，建议延迟一天建仓。'}
                </p>
              </div>
            </div>
          </div>

          {/* 交易参数与侧边栏 */}
          <div className="space-y-6">
            <div className="bg-gray-800/40 backdrop-blur-md border border-gray-700 rounded-2xl p-6 shadow-xl">
              <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span className="text-purple-400">⚙️</span> 建议交易参数
              </h4>
              {result.dynamic_params ? (
                <div className="space-y-4">
                  <div className="flex justify-between items-center p-3 bg-gray-900/50 rounded-xl">
                    <span className="text-gray-400">建议杠杆</span>
                    <span className="text-xl font-bold text-white">{result.dynamic_params.leverage}x</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-900/50 rounded-xl">
                    <span className="text-gray-400">止盈目标</span>
                    <span className="text-xl font-bold text-green-400">{(result.dynamic_params.profit_threshold * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-900/50 rounded-xl">
                    <span className="text-gray-400">初始止损</span>
                    <span className="text-xl font-bold text-red-400">{(result.dynamic_params.stop_loss_threshold * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-900/50 rounded-xl">
                    <span className="text-gray-400">补仓阈值</span>
                    <span className="text-xl font-bold text-orange-400">{(result.dynamic_params.add_position_threshold * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ) : (
                <p className="text-center text-gray-500 py-4 text-sm">该项目未提供动态参数建议</p>
              )}
            </div>

            {result.should_delay && result.delay_reasons && result.delay_reasons.length > 0 && (
              <div className="bg-yellow-900/20 border border-yellow-700/30 rounded-2xl p-6">
                <h4 className="text-yellow-400 font-bold mb-3 flex items-center gap-2 text-sm">
                  ⚠️ 延迟建仓原因
                </h4>
                <ul className="space-y-2">
                  {result.delay_reasons.map((reason, idx) => (
                    <li key={idx} className="text-sm text-yellow-200/70 flex items-start gap-2">
                      <span className="mt-1.5 w-1 h-1 bg-yellow-400 rounded-full flex-shrink-0" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
