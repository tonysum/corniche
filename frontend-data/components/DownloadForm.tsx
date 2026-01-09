'use client'

import { useState } from 'react'

const INTERVALS = [
  { value: '1m', label: '1分钟' },
  { value: '3m', label: '3分钟' },
  { value: '5m', label: '5分钟' },
  { value: '15m', label: '15分钟' },
  { value: '30m', label: '30分钟' },
  { value: '1h', label: '1小时' },
  { value: '2h', label: '2小时' },
  { value: '4h', label: '4小时' },
  { value: '6h', label: '6小时' },
  { value: '8h', label: '8小时' },
  { value: '12h', label: '12小时' },
  { value: '1d', label: '1天' },
  { value: '3d', label: '3天' },
  { value: '1w', label: '1周' },
  { value: '1M', label: '1月' },
]

import { API_URLS } from '../lib/api-config'
const API_BASE_URL = API_URLS.data

export default function DownloadForm() {
  const [formData, setFormData] = useState({
    interval: '1d',
    symbol: '',
    startTime: '2021-11-22 00:00:00',
    endTime: '',
    daysBack: '',
    limit: '',
    updateExisting: false,
    missingOnly: false,
    autoSplit: true,
    requestDelay: 0.1,
    batchSize: 30,
    batchDelay: 3.0,
  })
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)

    try {
      const payload: any = {
        interval: formData.interval,
        update_existing: formData.updateExisting,
        missing_only: formData.missingOnly,
        auto_split: formData.autoSplit,
        request_delay: formData.requestDelay,
        batch_size: formData.batchSize,
        batch_delay: formData.batchDelay,
      }

      // limit 可以为空（使用默认值）
      if (formData.limit) {
        payload.limit = parseInt(formData.limit) || undefined
      }

      if (formData.symbol) {
        payload.symbol = formData.symbol
      }

      if (formData.startTime) {
        payload.start_time = formData.startTime
      }

      if (formData.endTime) {
        payload.end_time = formData.endTime
      }

      if (formData.daysBack && !formData.startTime && !formData.endTime) {
        payload.days_back = parseInt(formData.daysBack)
      }

      const response = await fetch(`${API_BASE_URL}/api/download`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        let errorDetail = '下载失败'
        try {
          const errorData = await response.json()
          errorDetail = errorData.detail || errorData.message || `HTTP ${response.status}`
        } catch {
          errorDetail = `HTTP ${response.status}: ${response.statusText}`
        }
        throw new Error(errorDetail)
      }

      const data = await response.json()
      setMessage({
        type: 'success',
        text: data.message || '下载任务已启动',
      })
    } catch (error: any) {
      console.error('下载错误:', error)
      let errorMessage = '请求失败'
      
      if (error.message) {
        errorMessage = error.message
      } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
        errorMessage = `无法连接到后端服务器 (${API_BASE_URL})。请确保后端服务已启动。`
      } else {
        errorMessage = `请求失败: ${error.toString()}`
      }
      
      setMessage({
        type: 'error',
        text: errorMessage,
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-6">下载K线数据</h2>
      
      {message && (
        <div
          className={`mb-4 p-4 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-500/20 text-green-400 border border-green-500/50'
              : 'bg-red-500/20 text-red-400 border border-red-500/50'
          }`}
        >
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* K线间隔 */}
          <div>
            <label className="block text-sm font-medium mb-2">K线间隔 *</label>
            <select
              value={formData.interval}
              onChange={(e) => setFormData({ ...formData, interval: e.target.value })}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            >
              {INTERVALS.map((interval) => (
                <option key={interval.value} value={interval.value}>
                  {interval.label}
                </option>
              ))}
            </select>
          </div>

          {/* 交易对符号 */}
          <div>
            <label className="block text-sm font-medium mb-2">
              交易对符号（留空则下载所有交易对）
            </label>
            <input
              type="text"
              value={formData.symbol}
              onChange={(e) => setFormData({ ...formData, symbol: e.target.value.toUpperCase() })}
              placeholder="例如: BTCUSDT"
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* 开始时间 */}
          <div>
            <label className="block text-sm font-medium mb-2">
              开始时间（格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）
            </label>
            <input
              type="text"
              value={formData.startTime}
              onChange={(e) => setFormData({ ...formData, startTime: e.target.value })}
              placeholder="例如: 2025-01-01"
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* 结束时间 */}
          <div>
            <label className="block text-sm font-medium mb-2">
              结束时间（格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）
            </label>
            <input
              type="text"
              value={formData.endTime}
              onChange={(e) => setFormData({ ...formData, endTime: e.target.value })}
              placeholder="例如: 2025-12-31"
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* 回溯天数 */}
          <div>
            <label className="block text-sm font-medium mb-2">
              回溯天数（如果提供了开始/结束时间则忽略）
            </label>
            <input
              type="number"
              value={formData.daysBack}
              onChange={(e) => setFormData({ ...formData, daysBack: e.target.value })}
              placeholder="例如: 30"
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* 每次请求最大条数 */}
          <div>
            <label className="block text-sm font-medium mb-2">
              每次请求最大条数（留空使用默认1500）
            </label>
            <input
              type="number"
              value={formData.limit}
              onChange={(e) => setFormData({ ...formData, limit: e.target.value })}
              placeholder="默认: 1500"
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* 选项 */}
        <div className="flex flex-col space-y-3">
          <label className="flex items-center space-x-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={formData.updateExisting}
              onChange={(e) => setFormData({ ...formData, updateExisting: e.target.checked })}
              className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
            />
            <div className="flex flex-col">
              <span>更新已存在的数据</span>
              <span className="text-xs text-gray-400 mt-1">
                不勾选时，如果本地数据最后时间 &gt;= 结束时间会自动跳过下载
              </span>
            </div>
          </label>
          <label className="flex items-center space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.missingOnly}
              onChange={(e) => setFormData({ ...formData, missingOnly: e.target.checked })}
              className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
            />
            <span>只下载缺失的交易对</span>
          </label>
        </div>

        {/* 高级选项 */}
        <div className="border-t border-gray-700 pt-6">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center justify-between w-full text-left mb-4 text-gray-300 hover:text-white transition-colors"
          >
            <span className="font-medium">高级选项</span>
            <span className="text-xl">{showAdvanced ? '−' : '+'}</span>
          </button>
          
          {showAdvanced && (
            <div className="space-y-4 bg-gray-800/50 p-4 rounded-lg">
              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.autoSplit}
                  onChange={(e) => setFormData({ ...formData, autoSplit: e.target.checked })}
                  className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span>自动分段下载（当数据条数超过限制时自动分段）</span>
              </label>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    请求延迟（秒）
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={formData.requestDelay}
                    onChange={(e) => setFormData({ ...formData, requestDelay: parseFloat(e.target.value) || 0.1 })}
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-400 mt-1">默认: 0.1秒</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">
                    批次大小
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={formData.batchSize}
                    onChange={(e) => setFormData({ ...formData, batchSize: parseInt(e.target.value) || 30 })}
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-400 mt-1">默认: 30个交易对</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">
                    批次延迟（秒）
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={formData.batchDelay}
                    onChange={(e) => setFormData({ ...formData, batchDelay: parseFloat(e.target.value) || 3.0 })}
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-400 mt-1">默认: 3.0秒</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 提交按钮 */}
        <button
          type="submit"
          disabled={loading}
          className={`w-full py-3 px-6 rounded-lg font-medium transition-colors ${
            loading
              ? 'bg-gray-600 cursor-not-allowed'
              : 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700'
          }`}
        >
          {loading ? '下载中...' : '开始下载'}
        </button>
      </form>
    </div>
  )
}

