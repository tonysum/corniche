'use client'

import { useState } from 'react'

import { API_URLS } from '../lib/api-config'
const API_BASE_URL = API_URLS.data

export default function KlineViewer() {
  const [formData, setFormData] = useState({
    interval: '1d',
    symbol: '',
    startDate: '2021-11-22',
    endDate: '',
  })
  const [localData, setLocalData] = useState<any[]>([])
  const [binanceData, setBinanceData] = useState<any[]>([])
  const [loadingLocal, setLoadingLocal] = useState(false)
  const [loadingBinance, setLoadingBinance] = useState(false)
  const [errorLocal, setErrorLocal] = useState<string | null>(null)
  const [errorBinance, setErrorBinance] = useState<string | null>(null)

  // 获取本地数据
  const fetchLocalData = async () => {
    if (!formData.symbol) {
      setErrorLocal('请输入交易对符号')
      return
    }

    setLoadingLocal(true)
    setErrorLocal(null)
    try {
      let url = `${API_BASE_URL}/api/kline/${formData.interval}/${formData.symbol}`
      const params = new URLSearchParams()
      if (formData.startDate) params.append('start_date', formData.startDate)
      if (formData.endDate) params.append('end_date', formData.endDate)
      if (params.toString()) url += '?' + params.toString()

      const response = await fetch(url)
      
      if (!response.ok) {
        let errorDetail = '获取失败'
        try {
          const errorData = await response.json()
          errorDetail = errorData.detail || errorData.message || `HTTP ${response.status}`
        } catch {
          errorDetail = `HTTP ${response.status}: ${response.statusText}`
        }
        throw new Error(errorDetail)
      }
      
      const result = await response.json()
      const dataArray = result.data || []
      
      // 如果有友好的提示信息，显示给用户
      if (result.message && dataArray.length === 0) {
        setErrorLocal(result.message)
        setLocalData([])
        return
      }
      
      // 按日期降序排序（最新的数据在最上面）
      const sortedData = [...dataArray].sort((a, b) => {
        const dateA = new Date(a.trade_date).getTime()
        const dateB = new Date(b.trade_date).getTime()
        return dateB - dateA // 降序：最新的在前
      })
      
      setLocalData(sortedData)
    } catch (err: any) {
      console.error('获取本地K线数据错误:', err)
      let errorMessage = '请求失败'
      
      if (err.message) {
        errorMessage = err.message
      } else if (err.name === 'TypeError' && err.message.includes('fetch')) {
        errorMessage = `无法连接到后端服务器 (${API_BASE_URL})。请确保后端服务已启动。`
      } else {
        errorMessage = `请求失败: ${err.toString()}`
      }
      
      setErrorLocal(errorMessage)
    } finally {
      setLoadingLocal(false)
    }
  }

  // 获取币安API实时数据
  const fetchBinanceData = async () => {
    if (!formData.symbol) {
      setErrorBinance('请输入交易对符号')
      return
    }

    setLoadingBinance(true)
    setErrorBinance(null)
    try {
      let url = `${API_BASE_URL}/api/kline-binance/${formData.interval}/${formData.symbol}`
      const params = new URLSearchParams()
      if (formData.startDate) params.append('start_date', formData.startDate)
      if (formData.endDate) params.append('end_date', formData.endDate)
      // 不传limit参数，让后端根据日期范围自动计算和分段请求
      if (params.toString()) url += '?' + params.toString()

      const response = await fetch(url)
      
      if (!response.ok) {
        let errorDetail = '获取失败'
        try {
          const errorData = await response.json()
          // 提取友好的错误信息，避免显示技术细节
          if (errorData.detail) {
            // 如果是SQL错误或其他技术错误，显示友好提示
            if (errorData.detail.includes('no such table') || 
                errorData.detail.includes('OperationalError') ||
                errorData.detail.includes('SQL:')) {
              errorDetail = `币安API数据获取失败，请稍后重试`
            } else {
              errorDetail = errorData.detail
            }
          } else if (errorData.message) {
            errorDetail = errorData.message
          } else {
            errorDetail = `请求失败 (HTTP ${response.status})`
          }
        } catch {
          errorDetail = `请求失败 (HTTP ${response.status})`
        }
        throw new Error(errorDetail)
      }
      
      const result = await response.json()
      const dataArray = result.data || []
      
      // 币安API返回的数据已经是降序排序的，直接使用
      setBinanceData(dataArray)
    } catch (err: any) {
      console.error('获取币安API K线数据错误:', err)
      let errorMessage = '请求失败'
      
      if (err.message) {
        errorMessage = err.message
      } else if (err.name === 'TypeError' && err.message.includes('fetch')) {
        errorMessage = `无法连接到后端服务器 (${API_BASE_URL})。请确保后端服务已启动。`
      } else {
        errorMessage = `请求失败: ${err.toString()}`
      }
      
      setErrorBinance(errorMessage)
    } finally {
      setLoadingBinance(false)
    }
  }

  // 计算数据差异
  const calculateDataDiff = () => {
    if (localData.length === 0 && binanceData.length === 0) {
      return null
    }

    // 创建时间集合（标准化到分钟级别）
    const normalizeTime = (dateStr: string) => {
      const date = new Date(dateStr)
      date.setSeconds(0, 0)
      return date.getTime()
    }

    const localTimeSet = new Set(localData.map(item => normalizeTime(item.trade_date)))
    const binanceTimeSet = new Set(binanceData.map(item => normalizeTime(item.trade_date)))

    // 找出只在本地有的时间点
    const onlyInLocal = localData.filter(item => !binanceTimeSet.has(normalizeTime(item.trade_date)))
    
    // 找出只在币安API有的时间点
    const onlyInBinance = binanceData.filter(item => !localTimeSet.has(normalizeTime(item.trade_date)))
    
    // 找出共同的时间点
    const commonTimes = localData.filter(item => binanceTimeSet.has(normalizeTime(item.trade_date)))

    return {
      onlyInLocal,
      onlyInBinance,
      commonCount: commonTimes.length,
      localOnlyCount: onlyInLocal.length,
      binanceOnlyCount: onlyInBinance.length
    }
  }

  const dataDiff = calculateDataDiff()

  const INTERVALS = [
    { value: '1m', label: '1分钟' },
    { value: '5m', label: '5分钟' },
    { value: '15m', label: '15分钟' },
    { value: '1h', label: '1小时' },
    { value: '4h', label: '4小时' },
    { value: '1d', label: '1天' },
  ]

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">查看K线数据</h2>

      {/* 查询表单 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium mb-2">K线间隔</label>
          <select
            value={formData.interval}
            onChange={(e) => setFormData({ ...formData, interval: e.target.value })}
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {INTERVALS.map((int) => (
              <option key={int.value} value={int.value}>
                {int.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">交易对符号 *</label>
          <input
            type="text"
            value={formData.symbol}
            onChange={(e) => setFormData({ ...formData, symbol: e.target.value.toUpperCase() })}
            placeholder="例如: BTCUSDT"
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">开始日期</label>
          <input
            type="date"
            value={formData.startDate}
            onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">结束日期</label>
          <input
            type="date"
            value={formData.endDate}
            onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* 查询按钮 */}
      <div className="mb-6 flex gap-4">
        <button
          onClick={fetchLocalData}
          disabled={loadingLocal || !formData.symbol}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
        >
          {loadingLocal ? '查询中...' : '查询本地数据'}
        </button>
        <button
          onClick={fetchBinanceData}
          disabled={loadingBinance || !formData.symbol}
          className="px-6 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
        >
          {loadingBinance ? '查询中...' : '查询币安API数据'}
        </button>
      </div>

      {/* 数据差异提示 */}
      {dataDiff && (dataDiff.localOnlyCount > 0 || dataDiff.binanceOnlyCount > 0) && (
        <div className="mb-4 p-4 bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 rounded-lg">
          <div className="font-semibold mb-2">数据差异提示：</div>
          <div className="text-sm space-y-1">
            <div>共同时间点：{dataDiff.commonCount} 个</div>
            <div className="text-blue-400">仅在本地数据库：{dataDiff.localOnlyCount} 个</div>
            <div className="text-green-400">仅在币安API：{dataDiff.binanceOnlyCount} 个</div>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {(errorLocal || errorBinance) && (
        <div className="mb-4 space-y-2">
          {errorLocal && (
            <div className="p-4 bg-red-500/20 text-red-400 border border-red-500/50 rounded-lg">
              <strong>本地数据错误:</strong> {errorLocal}
            </div>
          )}
          {errorBinance && (
            <div className="p-4 bg-red-500/20 text-red-400 border border-red-500/50 rounded-lg">
              <strong>币安API错误:</strong> {errorBinance}
            </div>
          )}
        </div>
      )}

      {/* 两列数据表格 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 第一列：本地数据 */}
        <div>
          <h3 className="text-xl font-semibold mb-4 text-blue-400">
            本地数据库数据
            {loadingLocal && <span className="ml-2 text-sm text-gray-400">(加载中...)</span>}
          </h3>
          {localData.length > 0 ? (
            <div className="overflow-x-auto">
              <div className="mb-4 text-sm text-gray-400">
                共 {localData.length} 条记录
              </div>
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="bg-gray-700/50">
                    <th className="px-2 py-1.5 text-left border-b border-gray-600 whitespace-nowrap">日期</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">开盘价</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">最高价</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">最低价</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">收盘价</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">成交量</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">涨跌幅</th>
                  </tr>
                </thead>
                <tbody>
                  {localData.slice(0, 100).map((item: any, index: number) => (
                    <tr
                      key={index}
                      className="hover:bg-gray-700/30 transition-colors"
                    >
                      <td className="px-2 py-1.5 border-b border-gray-700 whitespace-nowrap">{item.trade_date}</td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 whitespace-nowrap">
                        {parseFloat(item.open).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 8,
                        })}
                      </td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 text-green-400 whitespace-nowrap">
                        {parseFloat(item.high).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 8,
                        })}
                      </td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 text-red-400 whitespace-nowrap">
                        {parseFloat(item.low).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 8,
                        })}
                      </td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 whitespace-nowrap">
                        {parseFloat(item.close).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 8,
                        })}
                      </td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 whitespace-nowrap">
                        {parseFloat(item.volume).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </td>
                      <td
                        className={`px-2 py-1.5 text-right border-b border-gray-700 whitespace-nowrap ${
                          item.pct_chg >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {item.pct_chg !== null && item.pct_chg !== undefined
                          ? `${(item.pct_chg * 100).toFixed(2)}%`
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {localData.length > 100 && (
                <div className="mt-4 text-sm text-gray-400 text-center">
                  仅显示前100条记录，共 {localData.length} 条
                </div>
              )}
            </div>
          ) : (
            <div className="text-gray-400 text-center py-8">
              {loadingLocal ? '加载中...' : '暂无数据'}
            </div>
          )}
        </div>

        {/* 第二列：币安API实时数据 */}
        <div>
          <h3 className="text-xl font-semibold mb-4 text-green-400">
            币安API实时数据
            {loadingBinance && <span className="ml-2 text-sm text-gray-400">(加载中...)</span>}
          </h3>
          {binanceData.length > 0 ? (
            <div className="overflow-x-auto">
              <div className="mb-4 text-sm text-gray-400">
                共 {binanceData.length} 条记录
              </div>
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="bg-gray-700/50">
                    <th className="px-2 py-1.5 text-left border-b border-gray-600 whitespace-nowrap">日期</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">开盘价</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">最高价</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">最低价</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">收盘价</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">成交量</th>
                    <th className="px-2 py-1.5 text-right border-b border-gray-600 whitespace-nowrap">涨跌幅</th>
                  </tr>
                </thead>
                <tbody>
                  {binanceData.slice(0, 100).map((item: any, index: number) => (
                    <tr
                      key={index}
                      className="hover:bg-gray-700/30 transition-colors"
                    >
                      <td className="px-2 py-1.5 border-b border-gray-700 whitespace-nowrap">{item.trade_date}</td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 whitespace-nowrap">
                        {parseFloat(item.open).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 8,
                        })}
                      </td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 text-green-400 whitespace-nowrap">
                        {parseFloat(item.high).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 8,
                        })}
                      </td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 text-red-400 whitespace-nowrap">
                        {parseFloat(item.low).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 8,
                        })}
                      </td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 whitespace-nowrap">
                        {parseFloat(item.close).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 8,
                        })}
                      </td>
                      <td className="px-2 py-1.5 text-right border-b border-gray-700 whitespace-nowrap">
                        {parseFloat(item.volume).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </td>
                      <td
                        className={`px-2 py-1.5 text-right border-b border-gray-700 whitespace-nowrap ${
                          item.pct_chg >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {item.pct_chg !== null && item.pct_chg !== undefined
                          ? `${(item.pct_chg * 100).toFixed(2)}%`
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {binanceData.length > 100 && (
                <div className="mt-4 text-sm text-gray-400 text-center">
                  仅显示前100条记录，共 {binanceData.length} 条
                </div>
              )}
            </div>
          ) : (
            <div className="text-gray-400 text-center py-8">
              {loadingBinance ? '加载中...' : '暂无数据'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

