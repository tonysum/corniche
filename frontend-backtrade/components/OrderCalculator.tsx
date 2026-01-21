'use client'

import { useState, useEffect } from 'react'
import { API_URLS } from '../lib/api-config'
import { useTopGainers } from '../contexts/TopGainersContext'

interface TopGainer {
  symbol: string
  pct_chg: number
  close: number | null
  open: number | null
  high: number | null
  low: number | null
  volume: number | null
}

interface TopGainer24h {
  symbol: string
  price_change_percent: number
  last_price: number | null
  open_price: number | null
  high_price: number | null
  low_price: number | null
  volume: number | null
}

interface TopGainerBinance {
  symbol: string
  pct_chg: number
  open: number
  close: number
  high: number
  low: number
  volume: number
}

interface OrderResult {
  entry_price: number | string
  stop_loss_price: number | string
  take_profit_price: number | string
}

export default function OrderCalculator() {
  const [price, setPrice] = useState('')
  const [entryPctChg, setEntryPctChg] = useState('1')
  const [lossThreshold, setLossThreshold] = useState('1.9')
  const [profitThreshold, setProfitThreshold] = useState('4')
  const [orderType, setOrderType] = useState<'short' | 'long'>('short')
  const [result, setResult] = useState<OrderResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  // 使用全局 Context 中的前一天涨幅数据
  const { topGainers, topGainersDate, loading: loadingTopGainers, error: topGainersError, refresh: refreshTopGainers } = useTopGainers()
  const [topGainers24h, setTopGainers24h] = useState<TopGainer24h[]>([])
  const [loadingTopGainers24h, setLoadingTopGainers24h] = useState(false)
  const [topGainersBinance, setTopGainersBinance] = useState<TopGainerBinance[]>([])
  const [loadingTopGainersBinance, setLoadingTopGainersBinance] = useState(false)
  const [selectedGainer, setSelectedGainer] = useState<TopGainer | null>(null)
  const [selectedGainer24h, setSelectedGainer24h] = useState<TopGainer24h | null>(null)
  const [selectedGainerBinance, setSelectedGainerBinance] = useState<TopGainerBinance | null>(null)

  const calculateOrder = async () => {
    setError('')
    setResult(null)

    // 验证输入
    if (!price || !entryPctChg || !lossThreshold || !profitThreshold) {
      setError('请填写所有字段')
      return
    }

    const priceNum = parseFloat(price)
    const entryPctChgNum = parseFloat(entryPctChg)
    const lossThresholdNum = parseFloat(lossThreshold)
    const profitThresholdNum = parseFloat(profitThreshold)

    if (isNaN(priceNum) || isNaN(entryPctChgNum) || isNaN(lossThresholdNum) || isNaN(profitThresholdNum)) {
      setError('请输入有效的数字')
      return
    }

    if (priceNum <= 0) {
      setError('价格必须大于0')
      return
    }

    setLoading(true)

    try {
      const response = await fetch(`${API_URLS.order}/api/calculate-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          price: priceNum,
          entry_pct_chg: entryPctChgNum,
          loss_threshold: lossThresholdNum,
          profit_threshold: profitThresholdNum,
          order_type: orderType,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '计算失败')
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '计算失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  // 当全局的前一天涨幅数据加载完成后，自动选择涨幅第一的交易对
  useEffect(() => {
    // 只有在24小时涨幅数据还没有加载时，才使用前一天涨幅第一作为默认
    // 如果24小时数据已加载，优先使用24小时涨幅第一
    if (topGainers.length > 0 && !selectedGainer24h && !loadingTopGainers) {
      const topGainer = topGainers[0]
      setSelectedGainer(topGainer)
      // 使用收盘价作为当前价格
      if (topGainer.close !== null) {
        setPrice(topGainer.close.toFixed(8))
        // 建仓涨幅保持用户设定的值，不随交易对涨幅变动
      }
    }
  }, [topGainers, selectedGainer24h, loadingTopGainers])

  // 当选中交易对和必要字段都设置后，自动计算订单价格
  useEffect(() => {
    const hasValidData = 
      (selectedGainer && selectedGainer.close !== null) || 
      (selectedGainer24h && selectedGainer24h.last_price !== null) ||
      (selectedGainerBinance && selectedGainerBinance.close !== null)
    
    if (hasValidData && price && entryPctChg && lossThreshold && profitThreshold) {
      // 延迟一下确保所有状态都已更新
      const timer = setTimeout(() => {
        calculateOrder()
      }, 300)
      return () => clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedGainer, selectedGainer24h, price, entryPctChg, lossThreshold, profitThreshold, orderType])

  // 处理点击前一天涨幅交易对
  const handleGainerClick = (gainer: TopGainer) => {
    setSelectedGainer(gainer)
    setSelectedGainer24h(null) // 清除24小时涨幅的选中状态
    // 设置价格，建仓涨幅保持用户设定的值
    if (gainer.close !== null) {
      setPrice(gainer.close.toFixed(8))
    }
  }

  // 处理点击24小时涨幅交易对
  const handleGainer24hClick = (gainer: TopGainer24h) => {
    setSelectedGainer24h(gainer)
    setSelectedGainer(null) // 清除前一天涨幅的选中状态
    setSelectedGainerBinance(null) // 清除交易所数据的选中状态
    // 设置价格，建仓涨幅保持用户设定的值
    if (gainer.last_price !== null) {
      setPrice(gainer.last_price.toFixed(8))
    }
  }

  // 处理点击交易所API计算的前一天涨幅交易对
  const handleGainerBinanceClick = (gainer: TopGainerBinance) => {
    setSelectedGainerBinance(gainer)
    setSelectedGainer(null) // 清除前一天涨幅的选中状态
    setSelectedGainer24h(null) // 清除24小时涨幅的选中状态
    // 设置价格，建仓涨幅保持用户设定的值
    setPrice(gainer.close.toFixed(8))
  }

  // 获取过去24小时涨幅前三
  useEffect(() => {
    const fetchTopGainers24h = async () => {
      setLoadingTopGainers24h(true)
      try {
        const response = await fetch(`${API_URLS.data}/api/top-gainers-24h?top_n=3`)
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        const data = await response.json()
        console.log('24小时涨幅数据:', data)
        const gainers24h = data.top_gainers || []
        setTopGainers24h(gainers24h)
        
        // 优先选择24小时涨幅第一的交易对并设置价格（默认选择）
        if (gainers24h.length > 0) {
          const topGainer24h = gainers24h[0]
          setSelectedGainer24h(topGainer24h)
          setSelectedGainer(null) // 清除前一天涨幅的选中状态
          setSelectedGainerBinance(null) // 清除交易所数据的选中状态
          // 使用最新价作为当前价格
          if (topGainer24h.last_price !== null) {
            setPrice(topGainer24h.last_price.toFixed(8))
            // 建仓涨幅保持用户设定的值，不随交易对涨幅变动
          }
        }
      } catch (err) {
        console.error('获取24小时涨幅排名失败:', err)
        setTopGainers24h([])
      } finally {
        setLoadingTopGainers24h(false)
      }
    }
    
    fetchTopGainers24h()
  }, [])

  // 获取前一天涨幅排名（交易所API计算）
  useEffect(() => {
    const fetchTopGainersBinance = async () => {
      setLoadingTopGainersBinance(true)
      try {
        const response = await fetch(`${API_URLS.data}/api/top-gainers-prev-day-binance?top_n=3`)
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        const data = await response.json()
        console.log('交易所API前一天涨幅数据:', data)
        const gainersBinance = data.top_gainers || []
        setTopGainersBinance(gainersBinance)
      } catch (err) {
        console.error('获取交易所API前一天涨幅排名失败:', err)
        setTopGainersBinance([])
      } finally {
        setLoadingTopGainersBinance(false)
      }
    }
    
    fetchTopGainersBinance()
  }, [])

  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-xl font-bold mb-1">合约下单计算</h2>
        <p className="text-gray-400 text-sm">计算建仓价格、止损价格、止盈价格</p>
      </div>

      {/* 过去24小时涨幅前三 */}
      <div className="bg-gradient-to-r from-green-900/50 to-teal-900/50 rounded-lg p-3 border border-green-700/50">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold">
            过去24小时涨幅前三
          </h3>
          {loadingTopGainers24h && (
            <span className="text-sm text-gray-400">加载中...</span>
          )}
        </div>
        
        {topGainers24h.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {topGainers24h.map((gainer, index) => (
              <div
                key={gainer.symbol}
                onClick={() => handleGainer24hClick(gainer)}
                className={`bg-gray-800/70 rounded-lg p-2 border cursor-pointer transition-all hover:scale-105 ${
                  selectedGainer24h?.symbol === gainer.symbol
                    ? 'border-blue-500 shadow-lg shadow-blue-500/30 ring-2 ring-blue-400'
                    : index === 0
                    ? 'border-yellow-500/50 shadow-lg shadow-yellow-500/20'
                    : index === 1
                    ? 'border-gray-500/50'
                    : 'border-gray-600/50'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-1">
                    <span className={`text-base font-bold ${
                      index === 0 ? 'text-yellow-400' : 'text-gray-300'
                    }`}>
                      #{index + 1}
                    </span>
                    <span className="font-semibold text-white text-sm">{gainer.symbol}</span>
                  </div>
                </div>
                <div className="space-y-0.5">
                  <div className="flex justify-between">
                    <span className="text-gray-400 text-sm">涨幅:</span>
                    <span className="text-green-400 font-bold">
                      +{gainer.price_change_percent.toFixed(2)}%
                    </span>
                  </div>
                  {gainer.last_price !== null && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-sm">最新价:</span>
                      <span className="text-gray-300">{gainer.last_price.toFixed(8)}</span>
                    </div>
                  )}
                  {gainer.volume !== null && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-sm">成交量:</span>
                      <span className="text-gray-300">
                        {gainer.volume >= 1000000
                          ? `${(gainer.volume / 1000000).toFixed(2)}M`
                          : gainer.volume >= 1000
                          ? `${(gainer.volume / 1000).toFixed(2)}K`
                          : gainer.volume.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : !loadingTopGainers24h ? (
          <div className="text-center py-2 text-gray-400 text-sm">
            暂无数据
          </div>
        ) : null}
      </div>

      {/* 前一天涨幅前三 */}
      <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg p-3 border border-blue-700/50">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold">
            前一天涨幅前三
            {topGainersDate && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                ({topGainersDate})
              </span>
            )}
          </h3>
          {loadingTopGainers && (
            <span className="text-sm text-gray-400">加载中...</span>
          )}
        </div>
        
        {topGainers.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {topGainers.map((gainer, index) => (
              <div
                key={gainer.symbol}
                onClick={() => handleGainerClick(gainer)}
                className={`bg-gray-800/70 rounded-lg p-2 border cursor-pointer transition-all hover:scale-105 ${
                  selectedGainer?.symbol === gainer.symbol
                    ? 'border-blue-500 shadow-lg shadow-blue-500/30 ring-2 ring-blue-400'
                    : index === 0
                    ? 'border-yellow-500/50 shadow-lg shadow-yellow-500/20'
                    : index === 1
                    ? 'border-gray-500/50'
                    : 'border-gray-600/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <span className={`text-lg font-bold ${
                      index === 0 ? 'text-yellow-400' : 'text-gray-300'
                    }`}>
                      #{index + 1}
                    </span>
                    <span className="font-semibold text-white">{gainer.symbol}</span>
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-gray-400 text-sm">涨幅:</span>
                    <span className="text-green-400 font-bold">
                      +{gainer.pct_chg.toFixed(2)}%
                    </span>
                  </div>
                  {gainer.close !== null && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-sm">收盘价:</span>
                      <span className="text-gray-300">{gainer.close.toFixed(8)}</span>
                    </div>
                  )}
                  {gainer.volume !== null && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-sm">成交量:</span>
                      <span className="text-gray-300">
                        {gainer.volume >= 1000000
                          ? `${(gainer.volume / 1000000).toFixed(2)}M`
                          : gainer.volume >= 1000
                          ? `${(gainer.volume / 1000).toFixed(2)}K`
                          : gainer.volume.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : !loadingTopGainers ? (
          <div className="text-center py-2 text-gray-400 text-sm space-y-2">
            <div>暂无数据</div>
            {topGainersDate && (
              <div className="text-xs text-gray-500">
                查询日期: {topGainersDate}
              </div>
            )}
            {topGainersError && (
              <div className="text-xs text-red-400 bg-red-900/20 px-2 py-1 rounded">
                {topGainersError}
              </div>
            )}
            <button
              onClick={() => refreshTopGainers()}
              className="mt-2 px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs transition-colors"
            >
              刷新数据
            </button>
          </div>
        ) : null}
      </div>

      {/* 前一天涨幅前三（交易所API计算） */}
      <div className="bg-gradient-to-r from-orange-900/50 to-amber-900/50 rounded-lg p-3 border border-orange-700/50">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold">
            前一天涨幅前三 (交易所数据计算)
          </h3>
          {loadingTopGainersBinance && (
            <span className="text-sm text-gray-400">加载中...</span>
          )}
        </div>
        
        {topGainersBinance.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {topGainersBinance.map((gainer, index) => (
              <div
                key={gainer.symbol}
                onClick={() => handleGainerBinanceClick(gainer)}
                className={`bg-gray-800/70 rounded-lg p-2 border cursor-pointer transition-all hover:scale-105 ${
                  selectedGainerBinance?.symbol === gainer.symbol
                    ? 'border-blue-500 shadow-lg shadow-blue-500/30 ring-2 ring-blue-400'
                    : index === 0
                    ? 'border-yellow-500/50 shadow-lg shadow-yellow-500/20'
                    : index === 1
                    ? 'border-gray-500/50'
                    : 'border-gray-600/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <span className={`text-lg font-bold ${
                      index === 0 ? 'text-yellow-400' : 'text-gray-300'
                    }`}>
                      #{index + 1}
                    </span>
                    <span className="font-semibold text-white">{gainer.symbol}</span>
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-gray-400 text-sm">涨幅:</span>
                    <span className="text-green-400 font-bold">
                      +{gainer.pct_chg.toFixed(2)}%
                    </span>
                  </div>
                  {gainer.close && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-sm">收盘价:</span>
                      <span className="text-gray-300">{gainer.close.toFixed(8)}</span>
                    </div>
                  )}
                  {gainer.volume && (
                    <div className="flex justify-between">
                      <span className="text-gray-400 text-sm">成交量:</span>
                      <span className="text-gray-300">
                        {gainer.volume >= 1000000
                          ? `${(gainer.volume / 1000000).toFixed(2)}M`
                          : gainer.volume >= 1000
                          ? `${(gainer.volume / 1000).toFixed(2)}K`
                          : gainer.volume.toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : !loadingTopGainersBinance ? (
          <div className="text-center py-2 text-gray-400 text-sm">
            暂无数据
          </div>
        ) : null}
      </div>

      <div className="bg-gray-700/50 rounded-lg p-4 space-y-4">
        {/* 订单类型选择 */}
        <div>
          <label className="block text-sm font-medium mb-1">订单类型</label>
          <div className="flex space-x-4">
            <button
              onClick={() => setOrderType('short')}
              className={`px-6 py-2 rounded-lg font-medium transition-all ${
                orderType === 'short'
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
              }`}
            >
              做空 (Short)
            </button>
            <button
              onClick={() => setOrderType('long')}
              className={`px-6 py-2 rounded-lg font-medium transition-all ${
                orderType === 'long'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
              }`}
            >
              做多 (Long)
            </button>
          </div>
        </div>

        {/* 输入表单 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">
              当前价格 <span className="text-red-400">*</span>
            </label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="例如: 10000"
              step="0.00000001"
              className="w-full px-4 py-2 bg-gray-600 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              建仓涨幅 (%) <span className="text-red-400">*</span>
            </label>
            <input
              type="number"
              value={entryPctChg}
              onChange={(e) => setEntryPctChg(e.target.value)}
              placeholder="例如: 1"
              step="0.01"
              className="w-full px-4 py-2 bg-gray-600 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              止损阈值 (%) <span className="text-red-400">*</span>
            </label>
            <input
              type="number"
              value={lossThreshold}
              onChange={(e) => setLossThreshold(e.target.value)}
              placeholder="例如: 1.9"
              step="0.01"
              className="w-full px-4 py-2 bg-gray-600 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              止盈阈值 (%) <span className="text-red-400">*</span>
            </label>
            <input
              type="number"
              value={profitThreshold}
              onChange={(e) => setProfitThreshold(e.target.value)}
              placeholder="例如: 4"
              step="0.01"
              className="w-full px-4 py-2 bg-gray-600 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* 计算按钮 */}
        <button
          onClick={calculateOrder}
          disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
        >
          {loading ? '计算中...' : '计算订单价格'}
        </button>

        {/* 错误提示 */}
        {error && (
          <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
            {error}
          </div>
        )}

        {/* 结果显示 */}
        {result && (
          <div className="p-4 bg-gray-600/50 rounded-lg border border-gray-500 space-y-3">
            <h3 className="text-base font-bold mb-2">计算结果</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="bg-gray-700/50 p-3 rounded-lg">
                <div className="text-xs text-gray-400 mb-1">建仓价格</div>
                <div className="text-xl font-bold text-blue-400">
                  {typeof result.entry_price === 'string' ? result.entry_price : result.entry_price.toFixed(8)}
                </div>
              </div>

              <div className="bg-gray-700/50 p-3 rounded-lg">
                <div className="text-xs text-gray-400 mb-1">止损价格</div>
                <div className="text-xl font-bold text-red-400">
                  {typeof result.stop_loss_price === 'string' ? result.stop_loss_price : result.stop_loss_price.toFixed(8)}
                </div>
              </div>

              <div className="bg-gray-700/50 p-3 rounded-lg">
                <div className="text-xs text-gray-400 mb-1">止盈价格</div>
                <div className="text-xl font-bold text-green-400">
                  {typeof result.take_profit_price === 'string' ? result.take_profit_price : result.take_profit_price.toFixed(8)}
                </div>
              </div>
            </div>

            {/* 价格差异显示 */}
            <div className="mt-2 pt-2 border-t border-gray-600 space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">建仓价格 vs 当前价格:</span>
                <span className={parseFloat(String(result.entry_price)) > parseFloat(price) ? 'text-red-400' : 'text-green-400'}>
                  {orderType === 'short' ? '+' : '-'}
                  {Math.abs(parseFloat(String(result.entry_price)) - parseFloat(price)).toFixed(8)} (
                  {((Math.abs(parseFloat(String(result.entry_price)) - parseFloat(price)) / parseFloat(price)) * 100).toFixed(2)}%)
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">止损价格 vs 建仓价格:</span>
                <span className="text-red-400">
                  {orderType === 'short' ? '+' : '-'}
                  {Math.abs(parseFloat(String(result.stop_loss_price)) - parseFloat(String(result.entry_price))).toFixed(8)} (
                  {((Math.abs(parseFloat(String(result.stop_loss_price)) - parseFloat(String(result.entry_price))) / parseFloat(String(result.entry_price))) * 100).toFixed(2)}%)
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">止盈价格 vs 建仓价格:</span>
                <span className="text-green-400">
                  {orderType === 'short' ? '-' : '+'}
                  {Math.abs(parseFloat(String(result.entry_price)) - parseFloat(String(result.take_profit_price))).toFixed(8)} (
                  {((Math.abs(parseFloat(String(result.entry_price)) - parseFloat(String(result.take_profit_price))) / parseFloat(String(result.entry_price))) * 100).toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

