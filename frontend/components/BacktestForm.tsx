'use client'

import { useState } from 'react'
import { API_URLS } from '../lib/api-config'

interface BacktestResult {
  initial_capital: number
  final_capital: number
  total_profit_loss: number
  total_return_rate: number
  total_trades: number
  win_trades: number
  loss_trades: number
  win_rate: number
  long_trades?: number
  short_trades?: number
  strategy?: string
  csv_filename?: string
}

export default function BacktestForm() {
  const [backtestType, setBacktestType] = useState<'standard' | 'smartmoney'>('standard')
  const [startDate, setStartDate] = useState('2025-11-01')
  const [endDate, setEndDate] = useState('2026-01-03')
  const [initialCapital, setInitialCapital] = useState('10000')
  const [leverage, setLeverage] = useState('20')
  const [profitThreshold, setProfitThreshold] = useState('6.5')
  const [lossThreshold, setLossThreshold] = useState('1.9')
  const [positionSizeRatio, setPositionSizeRatio] = useState('5')
  const [minPctChg, setMinPctChg] = useState('10')
  const [delayEntry, setDelayEntry] = useState(false)
  const [delayHours, setDelayHours] = useState('12')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const runBacktest = async () => {
    setError('')
    setResult(null)

    if (!startDate || !endDate) {
      setError('请填写开始日期和结束日期')
      return
    }

    if (new Date(startDate) > new Date(endDate)) {
      setError('开始日期不能晚于结束日期')
      return
    }

    // 聪明钱回测只需要日期参数
    if (backtestType === 'smartmoney') {
      setLoading(true)
      try {
        const response = await fetch(`${API_URLS.backtest}/api/backtest/smartmoney`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            start_date: startDate,
            end_date: endDate,
          }),
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || '回测失败')
        }

        const data = await response.json()
        setResult(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : '回测失败，请稍后重试')
      } finally {
        setLoading(false)
      }
      return
    }

    // 标准回测需要验证策略参数
    const initialCapitalNum = parseFloat(initialCapital)
    const leverageNum = parseFloat(leverage)
    const profitThresholdNum = parseFloat(profitThreshold)
    const lossThresholdNum = parseFloat(lossThreshold)
    const positionSizeRatioNum = parseFloat(positionSizeRatio)
    const minPctChgNum = parseFloat(minPctChg)

    if (isNaN(initialCapitalNum) || initialCapitalNum <= 0) {
      setError('初始资金必须大于0')
      return
    }
    if (isNaN(leverageNum) || leverageNum <= 0) {
      setError('杠杆倍数必须大于0')
      return
    }
    if (isNaN(profitThresholdNum) || profitThresholdNum < 0 || profitThresholdNum > 100) {
      setError('止盈阈值必须在0-100之间')
      return
    }
    if (isNaN(lossThresholdNum) || lossThresholdNum < 0 || lossThresholdNum > 100) {
      setError('止损阈值必须在0-100之间')
      return
    }
    if (isNaN(positionSizeRatioNum) || positionSizeRatioNum <= 0 || positionSizeRatioNum > 100) {
      setError('建仓比例必须在0-100之间')
      return
    }
    if (isNaN(minPctChgNum) || minPctChgNum < 0) {
      setError('最小涨幅必须大于等于0')
      return
    }

    const delayHoursNum = parseFloat(delayHours)
    if (delayEntry && (isNaN(delayHoursNum) || delayHoursNum <= 0)) {
      setError('延迟小时数必须大于0')
      return
    }

    setLoading(true)

    try {
      const response = await fetch(`${API_URLS.backtest}/api/backtest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          start_date: startDate,
          end_date: endDate,
          initial_capital: initialCapitalNum,
          leverage: leverageNum,
          profit_threshold: profitThresholdNum / 100, // 转换为小数
          loss_threshold: lossThresholdNum / 100, // 转换为小数
          position_size_ratio: positionSizeRatioNum / 100, // 转换为小数
          min_pct_chg: minPctChgNum / 100, // 转换为小数
          delay_entry: delayEntry,
          delay_hours: delayEntry ? delayHoursNum : 12,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '回测失败')
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '回测失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">回测交易</h2>
        <p className="text-gray-400">根据历史K线数据模拟交易策略</p>
      </div>

      {/* 回测类型标签页 */}
      <div className="flex space-x-4 border-b border-gray-700">
        <button
          onClick={() => {
            setBacktestType('standard')
            setResult(null)
            setError('')
          }}
          className={`px-6 py-3 font-medium transition-colors ${
            backtestType === 'standard'
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          标准回测
        </button>
        <button
          onClick={() => {
            setBacktestType('smartmoney')
            setResult(null)
            setError('')
          }}
          className={`px-6 py-3 font-medium transition-colors ${
            backtestType === 'smartmoney'
              ? 'text-purple-400 border-b-2 border-purple-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          聪明钱回测
        </button>
      </div>

      <div className="bg-gray-700/50 rounded-lg p-6 space-y-6">
        {/* 输入表单 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              开始日期 <span className="text-red-400">*</span>
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-4 py-2 bg-gray-600 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              结束日期 <span className="text-red-400">*</span>
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-4 py-2 bg-gray-600 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* 聪明钱策略说明 */}
        {backtestType === 'smartmoney' && (
          <div className="bg-purple-900/30 border border-purple-700 rounded-lg p-4">
            <h3 className="font-bold text-purple-300 mb-3">聪明钱策略特点</h3>
            <ul className="space-y-2 text-sm text-purple-200">
              <li>• <strong>动态杠杆策略</strong>：根据入场涨幅动态调整杠杆、止盈、止损</li>
              <li>• <strong>双向交易模式</strong>：支持做多和做空，根据巨鲸数据分析决定交易方向</li>
              <li>• <strong>成交额分级仓位</strong>：根据24h成交额动态调整仓位大小</li>
              <li>• <strong>入场等待机制</strong>：等待开盘价上涨一定幅度后再建仓，避免追高被套</li>
              <li>• <strong>实盘风控系统</strong>：基于币安期货API获取实时市场情绪数据</li>
            </ul>
            <p className="mt-3 text-xs text-purple-300">
              注意：聪明钱策略使用全局配置参数，不支持自定义参数。只需选择日期范围即可开始回测。
            </p>
          </div>
        )}

        {/* 策略参数（仅标准回测显示） */}
        {backtestType === 'standard' && (
          <div className="bg-gray-600/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-white">策略参数</h3>
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                {showAdvanced ? '收起 ▲' : '展开 ▼'}
              </button>
            </div>
            
            {showAdvanced && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  初始资金 (USDT) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(e.target.value)}
                  placeholder="例如: 700"
                  step="0.01"
                  min="0"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  杠杆倍数 <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={leverage}
                  onChange={(e) => setLeverage(e.target.value)}
                  placeholder="例如: 20"
                  step="0.1"
                  min="0"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  止盈阈值 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={profitThreshold}
                  onChange={(e) => setProfitThreshold(e.target.value)}
                  placeholder="例如: 4"
                  step="0.1"
                  min="0"
                  max="100"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  止损阈值 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={lossThreshold}
                  onChange={(e) => setLossThreshold(e.target.value)}
                  placeholder="例如: 1.9"
                  step="0.1"
                  min="0"
                  max="100"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  建仓比例 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={positionSizeRatio}
                  onChange={(e) => setPositionSizeRatio(e.target.value)}
                  placeholder="例如: 6"
                  step="0.1"
                  min="0"
                  max="100"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                />
                <p className="text-xs text-gray-400 mt-1">每次建仓金额占账户余额的百分比</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  最小涨幅 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={minPctChg}
                  onChange={(e) => setMinPctChg(e.target.value)}
                  placeholder="例如: 10"
                  step="0.1"
                  min="0"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                />
                <p className="text-xs text-gray-400 mt-1">达到此涨幅才建仓</p>
              </div>

              <div>
                <label className="flex items-center text-sm font-medium mb-2 text-gray-300">
                  <input
                    type="checkbox"
                    checked={delayEntry}
                    onChange={(e) => setDelayEntry(e.target.checked)}
                    className="mr-2 w-4 h-4"
                  />
                  启用延迟入场策略
                </label>
                <p className="text-xs text-gray-400 mt-1 ml-6">等待涨势减弱后再建仓（需要1小时K线数据）</p>
              </div>

              {delayEntry && (
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-300">
                    延迟小时数 <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={delayHours}
                    onChange={(e) => setDelayHours(e.target.value)}
                    placeholder="例如: 12"
                    step="1"
                    min="1"
                    max="24"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                  />
                  <p className="text-xs text-gray-400 mt-1">等待多少小时后开始监控涨势减弱</p>
                </div>
              )}
            </div>
          )}

            {/* 策略说明 */}
            <div className="mt-4 text-sm text-gray-300">
              <h4 className="font-bold mb-2 text-white">当前策略参数：</h4>
              <ul className="space-y-1 list-disc list-inside">
                <li>初始资金：{initialCapital} USDT</li>
                <li>杠杆：{leverage}倍</li>
                <li>每次建仓金额：账户余额的{positionSizeRatio}%</li>
                <li>建仓条件：涨幅≥{minPctChg}% 且 该交易对未持仓</li>
                <li>建仓方向：卖空（做空）</li>
                {delayEntry ? (
                  <>
                    <li>入场策略：<span className="text-yellow-400">延迟入场</span> - 等待{delayHours}小时，涨势减弱后建仓</li>
                    <li className="text-xs text-gray-400 ml-4">需要1小时K线数据支持</li>
                  </>
                ) : (
                  <li>入场策略：立即入场 - 第二天开盘价建仓</li>
                )}
                <li>止盈：价格下跌{profitThreshold}%时盈利平仓</li>
                <li>止损：价格上涨{lossThreshold}%时止损平仓</li>
                <li>支持同时持有多个仓位</li>
              </ul>
            </div>
          </div>
        )}

        {/* 运行按钮 */}
        <button
          onClick={runBacktest}
          disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
        >
          {loading ? '回测中...' : '开始回测'}
        </button>

        {/* 错误提示 */}
        {error && (
          <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
            {error}
          </div>
        )}

        {/* 结果显示 */}
        {result && (
          <div className="p-6 bg-gray-600/50 rounded-lg border border-gray-500 space-y-4">
            <h3 className="text-lg font-bold mb-4">回测结果</h3>
            
            {/* 主要指标 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-gray-700/50 p-4 rounded-lg">
                <div className="text-sm text-gray-400 mb-1">初始资金</div>
                <div className="text-2xl font-bold text-blue-400">
                  {result.initial_capital.toFixed(2)} USDT
                </div>
              </div>

              <div className="bg-gray-700/50 p-4 rounded-lg">
                <div className="text-sm text-gray-400 mb-1">最终资金</div>
                <div className={`text-2xl font-bold ${
                  result.final_capital >= result.initial_capital ? 'text-green-400' : 'text-red-400'
                }`}>
                  {result.final_capital.toFixed(2)} USDT
                </div>
              </div>

              <div className="bg-gray-700/50 p-4 rounded-lg">
                <div className="text-sm text-gray-400 mb-1">总盈亏</div>
                <div className={`text-2xl font-bold ${
                  result.total_profit_loss >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {result.total_profit_loss >= 0 ? '+' : ''}
                  {result.total_profit_loss.toFixed(2)} USDT
                </div>
              </div>

              <div className="bg-gray-700/50 p-4 rounded-lg">
                <div className="text-sm text-gray-400 mb-1">总收益率</div>
                <div className={`text-2xl font-bold ${
                  result.total_return_rate >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {result.total_return_rate >= 0 ? '+' : ''}
                  {result.total_return_rate.toFixed(2)}%
                </div>
              </div>
            </div>

            {/* 交易统计 */}
            <div className="mt-4 pt-4 border-t border-gray-600">
              <h4 className="font-bold mb-3">交易统计</h4>
              <div className={`grid grid-cols-2 ${result.long_trades !== undefined ? 'md:grid-cols-6' : 'md:grid-cols-4'} gap-4 text-sm`}>
                <div>
                  <div className="text-gray-400">交易次数</div>
                  <div className="text-xl font-bold text-white">{result.total_trades}</div>
                </div>
                <div>
                  <div className="text-gray-400">盈利次数</div>
                  <div className="text-xl font-bold text-green-400">{result.win_trades}</div>
                </div>
                <div>
                  <div className="text-gray-400">亏损次数</div>
                  <div className="text-xl font-bold text-red-400">{result.loss_trades}</div>
                </div>
                <div>
                  <div className="text-gray-400">胜率</div>
                  <div className="text-xl font-bold text-blue-400">{result.win_rate.toFixed(2)}%</div>
                </div>
                {result.long_trades !== undefined && (
                  <>
                    <div>
                      <div className="text-gray-400">做多次数</div>
                      <div className="text-xl font-bold text-green-300">{result.long_trades}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">做空次数</div>
                      <div className="text-xl font-bold text-red-300">{result.short_trades}</div>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* CSV文件提示 */}
            {result.csv_filename && (
              <div className="mt-4 p-3 bg-blue-900/30 border border-blue-700 rounded-lg text-sm text-blue-200">
                <span className="font-medium">交易记录已保存到CSV文件：</span>
                <span className="ml-2 font-mono">{result.csv_filename}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

