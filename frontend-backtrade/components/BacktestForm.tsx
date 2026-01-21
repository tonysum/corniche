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
  max_drawdown?: number
}

export default function BacktestForm() {
  const [backtestType, setBacktestType] = useState<'standard' | 'smartmoney' | 'buy-surge' | 'backtrade4'>('standard')
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
  // 聪明钱回测参数
  const [smartMoneyInitialCapital, setSmartMoneyInitialCapital] = useState('10000')
  const [enableDynamicLeverage, setEnableDynamicLeverage] = useState(true)
  const [enableLongTrade, setEnableLongTrade] = useState(true)
  const [tradeDirection, setTradeDirection] = useState<'short' | 'long' | 'auto'>('auto')
  const [enableVolumePositionSizing, setEnableVolumePositionSizing] = useState(true)
  const [enableRiskControl, setEnableRiskControl] = useState(true)
  const [smartMoneyPositionSizeRatio, setSmartMoneyPositionSizeRatio] = useState('10')
  const [smartMoneyMinPctChg, setSmartMoneyMinPctChg] = useState('25')
  const [showSmartMoneyAdvanced, setShowSmartMoneyAdvanced] = useState(false)
  // 买量暴涨回测参数
  const [buySurgeInitialCapital, setBuySurgeInitialCapital] = useState('10000')
  const [buySurgeLeverage, setBuySurgeLeverage] = useState('4')
  const [buySurgePositionSizeRatio, setBuySurgePositionSizeRatio] = useState('5')
  const [buySurgeThreshold, setBuySurgeThreshold] = useState('20.0')
  const [buySurgeTakeProfitPct, setBuySurgeTakeProfitPct] = useState('20')
  const [buySurgeAddPositionTriggerPct, setBuySurgeAddPositionTriggerPct] = useState('-18')
  const [buySurgeStopLossPct, setBuySurgeStopLossPct] = useState('-18')
  const [buySurgeMaxHoldHours, setBuySurgeMaxHoldHours] = useState('72')
  const [buySurgeWaitTimeoutHours, setBuySurgeWaitTimeoutHours] = useState('48')
  const [showBuySurgeAdvanced, setShowBuySurgeAdvanced] = useState(false)
  // Backtrade4回测参数
  const [backtrade4InitialCapital, setBacktrade4InitialCapital] = useState('10000')
  const [backtrade4PositionSizeRatio, setBacktrade4PositionSizeRatio] = useState('10')
  const [backtrade4MinPctChg, setBacktrade4MinPctChg] = useState('25')
  const [backtrade4EnableDynamicLeverage, setBacktrade4EnableDynamicLeverage] = useState(true)
  const [backtrade4EnableLongTrade, setBacktrade4EnableLongTrade] = useState(true)
  const [backtrade4TradeDirection, setBacktrade4TradeDirection] = useState<'short' | 'long' | 'auto'>('auto')
  const [backtrade4EnableVolumePositionSizing, setBacktrade4EnableVolumePositionSizing] = useState(true)
  const [backtrade4EnableRiskControl, setBacktrade4EnableRiskControl] = useState(false)
  const [showBacktrade4Advanced, setShowBacktrade4Advanced] = useState(false)
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

    // 买量暴涨回测
    if (backtestType === 'buy-surge') {
      // 验证参数
      const initialCapitalNum = parseFloat(buySurgeInitialCapital)
      const leverageNum = parseFloat(buySurgeLeverage)
      const positionSizeRatioNum = parseFloat(buySurgePositionSizeRatio)
      const thresholdNum = parseFloat(buySurgeThreshold)
      const takeProfitPctNum = parseFloat(buySurgeTakeProfitPct)
      const addPositionTriggerPctNum = parseFloat(buySurgeAddPositionTriggerPct)
      const stopLossPctNum = parseFloat(buySurgeStopLossPct)
      const maxHoldHoursNum = parseFloat(buySurgeMaxHoldHours)
      const waitTimeoutHoursNum = parseFloat(buySurgeWaitTimeoutHours)

      if (isNaN(initialCapitalNum) || initialCapitalNum <= 0) {
        setError('初始资金必须大于0')
        return
      }
      if (isNaN(leverageNum) || leverageNum <= 0) {
        setError('杠杆倍数必须大于0')
        return
      }
      if (isNaN(positionSizeRatioNum) || positionSizeRatioNum <= 0 || positionSizeRatioNum > 100) {
        setError('建仓比例必须在0-100之间')
        return
      }
      if (isNaN(thresholdNum) || thresholdNum <= 0) {
        setError('买量暴涨阈值必须大于0')
        return
      }
      if (isNaN(takeProfitPctNum) || takeProfitPctNum < 0 || takeProfitPctNum > 100) {
        setError('止盈比例必须在0-100之间')
        return
      }
      if (isNaN(addPositionTriggerPctNum) || addPositionTriggerPctNum > 0) {
        setError('补仓触发比例必须是负数')
        return
      }
      if (isNaN(stopLossPctNum) || stopLossPctNum > 0) {
        setError('止损比例必须是负数')
        return
      }
      if (isNaN(maxHoldHoursNum) || maxHoldHoursNum <= 0) {
        setError('最大持仓小时数必须大于0')
        return
      }
      if (isNaN(waitTimeoutHoursNum) || waitTimeoutHoursNum <= 0) {
        setError('等待超时时间必须大于0')
        return
      }

      setLoading(true)
      try {
        const response = await fetch(`${API_URLS.backtest}/api/backtest/buy-surge`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            start_date: startDate,
            end_date: endDate,
            initial_capital: initialCapitalNum,
            leverage: leverageNum,
            position_size_ratio: positionSizeRatioNum / 100, // 转换为小数
            buy_surge_threshold: thresholdNum,
            take_profit_pct: takeProfitPctNum / 100, // 转换为小数
            add_position_trigger_pct: addPositionTriggerPctNum / 100, // 转换为小数
            stop_loss_pct: stopLossPctNum / 100, // 转换为小数
            max_hold_hours: maxHoldHoursNum,
            wait_timeout_hours: waitTimeoutHoursNum,
          }),
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || '回测失败')
        }

        const data = await response.json()
        // 转换返回数据格式以匹配BacktestResult接口
        setResult({
          initial_capital: data.statistics?.initial_capital || data.initial_capital || 0,
          final_capital: data.statistics?.final_capital || data.final_capital || 0,
          total_profit_loss: (data.statistics?.final_capital || 0) - (data.statistics?.initial_capital || 0),
          total_return_rate: data.statistics?.total_return || data.total_return_rate || 0,
          total_trades: data.statistics?.total_trades || data.total_trades || 0,
          win_trades: data.statistics?.winning_trades || data.win_trades || 0,
          loss_trades: data.statistics?.losing_trades || data.loss_trades || 0,
          win_rate: data.statistics?.win_rate || data.win_rate || 0,
          max_drawdown: data.statistics?.max_drawdown,
          strategy: data.strategy || '买量暴涨策略',
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : '回测失败，请稍后重试')
      } finally {
        setLoading(false)
      }
      return
    }

    // 聪明钱回测
    if (backtestType === 'smartmoney') {
      // 验证参数
      const initialCapitalNum = parseFloat(smartMoneyInitialCapital)
      const positionSizeRatioNum = parseFloat(smartMoneyPositionSizeRatio)
      const minPctChgNum = parseFloat(smartMoneyMinPctChg)

      if (isNaN(initialCapitalNum) || initialCapitalNum <= 0) {
        setError('初始资金必须大于0')
        return
      }
      if (isNaN(positionSizeRatioNum) || positionSizeRatioNum <= 0 || positionSizeRatioNum > 100) {
        setError('基础仓位比例必须在0-100之间')
        return
      }
      if (isNaN(minPctChgNum) || minPctChgNum < 0) {
        setError('最小涨幅必须大于等于0')
        return
      }
      if (!['short', 'long', 'auto'].includes(tradeDirection)) {
        setError('交易方向必须是 short、long 或 auto')
        return
      }

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
            initial_capital: initialCapitalNum,
            enable_dynamic_leverage: enableDynamicLeverage,
            enable_long_trade: enableLongTrade,
            trade_direction: tradeDirection,
            enable_volume_position_sizing: enableVolumePositionSizing,
            enable_risk_control: enableRiskControl,
            position_size_ratio: positionSizeRatioNum / 100, // 转换为小数
            min_pct_chg: minPctChgNum / 100, // 转换为小数
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

    // Backtrade4回测
    if (backtestType === 'backtrade4') {
      // 验证参数
      const initialCapitalNum = parseFloat(backtrade4InitialCapital)
      const positionSizeRatioNum = parseFloat(backtrade4PositionSizeRatio)
      const minPctChgNum = parseFloat(backtrade4MinPctChg)

      if (isNaN(initialCapitalNum) || initialCapitalNum <= 0) {
        setError('初始资金必须大于0')
        return
      }
      if (isNaN(positionSizeRatioNum) || positionSizeRatioNum <= 0 || positionSizeRatioNum > 100) {
        setError('基础仓位比例必须在0-100之间')
        return
      }
      if (isNaN(minPctChgNum) || minPctChgNum < 0) {
        setError('最小涨幅必须大于等于0')
        return
      }

      setLoading(true)
      try {
        const response = await fetch(`${API_URLS.backtest}/api/backtest/backtrade4`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            start_date: startDate,
            end_date: endDate,
            initial_capital: initialCapitalNum,
            enable_dynamic_leverage: backtrade4EnableDynamicLeverage,
            enable_long_trade: backtrade4EnableLongTrade,
            trade_direction: backtrade4TradeDirection,
            enable_volume_position_sizing: backtrade4EnableVolumePositionSizing,
            enable_risk_control: backtrade4EnableRiskControl,
            position_size_ratio: positionSizeRatioNum / 100, // 转换为小数
            min_pct_chg: minPctChgNum / 100, // 转换为小数
          }),
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || '回测失败')
        }

        const data = await response.json()
        // 转换数据格式以匹配前端显示
        setResult({
          initial_capital: data.statistics?.initial_capital || 0,
          final_capital: data.statistics?.final_capital || 0,
          total_profit_loss: data.statistics?.total_profit_loss || 0,
          total_return_rate: data.statistics?.total_return_rate || 0,
          total_trades: data.statistics?.total_trades || 0,
          win_trades: data.statistics?.win_trades || 0,
          loss_trades: data.statistics?.loss_trades || 0,
          win_rate: data.statistics?.win_rate || 0,
          strategy: data.strategy,
          csv_filename: data.csv_filename
        })
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
        <button
          onClick={() => {
            setBacktestType('buy-surge')
            setResult(null)
            setError('')
          }}
          className={`px-6 py-3 font-medium transition-colors ${
            backtestType === 'buy-surge'
              ? 'text-orange-400 border-b-2 border-orange-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          买量暴涨回测
        </button>
        <button
          onClick={() => {
            setBacktestType('backtrade4')
            setResult(null)
            setError('')
          }}
          className={`px-6 py-3 font-medium transition-colors ${
            backtestType === 'backtrade4'
              ? 'text-green-400 border-b-2 border-green-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          Backtrade4回测
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

        {/* 买量暴涨策略参数设置 */}
        {backtestType === 'buy-surge' && (
          <div className="bg-orange-900/30 border border-orange-700 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-orange-300">买量暴涨策略参数</h3>
              <button
                onClick={() => setShowBuySurgeAdvanced(!showBuySurgeAdvanced)}
                className="text-sm text-orange-400 hover:text-orange-300 transition-colors"
              >
                {showBuySurgeAdvanced ? '收起 ▲' : '展开 ▼'}
              </button>
            </div>

            {/* 基础参数 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2 text-orange-200">
                  初始资金 (USDT) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={buySurgeInitialCapital}
                  onChange={(e) => setBuySurgeInitialCapital(e.target.value)}
                  placeholder="例如: 10000"
                  step="0.01"
                  min="0"
                  className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-orange-200">
                  杠杆倍数 <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={buySurgeLeverage}
                  onChange={(e) => setBuySurgeLeverage(e.target.value)}
                  placeholder="例如: 4"
                  step="0.1"
                  min="0"
                  className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                />
                <p className="text-xs text-orange-300 mt-1">默认4倍</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-orange-200">
                  建仓比例 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={buySurgePositionSizeRatio}
                  onChange={(e) => setBuySurgePositionSizeRatio(e.target.value)}
                  placeholder="例如: 5"
                  step="0.1"
                  min="0"
                  max="100"
                  className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                />
                <p className="text-xs text-orange-300 mt-1">单次建仓占资金比例，默认5%</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-orange-200">
                  买量暴涨阈值 (倍) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={buySurgeThreshold}
                  onChange={(e) => setBuySurgeThreshold(e.target.value)}
                  placeholder="例如: 20.0"
                  step="0.1"
                  min="0"
                  className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                />
                <p className="text-xs text-orange-300 mt-1">当日买量/昨日买量，默认20倍</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-orange-200">
                  止盈比例 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={buySurgeTakeProfitPct}
                  onChange={(e) => setBuySurgeTakeProfitPct(e.target.value)}
                  placeholder="例如: 20"
                  step="0.1"
                  min="0"
                  max="100"
                  className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                />
                <p className="text-xs text-orange-300 mt-1">基础止盈20%，动态调整可达30%</p>
              </div>
            </div>

            {/* 高级参数 */}
            {showBuySurgeAdvanced && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-orange-700">
                <div>
                  <label className="block text-sm font-medium mb-2 text-orange-200">
                    补仓触发比例 (%) <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={buySurgeAddPositionTriggerPct}
                    onChange={(e) => setBuySurgeAddPositionTriggerPct(e.target.value)}
                    placeholder="例如: -18"
                    step="0.1"
                    max="0"
                    className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                  />
                  <p className="text-xs text-orange-300 mt-1">价格下跌此比例时补仓，默认-18%</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-orange-200">
                    止损比例 (%) <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={buySurgeStopLossPct}
                    onChange={(e) => setBuySurgeStopLossPct(e.target.value)}
                    placeholder="例如: -18"
                    step="0.1"
                    max="0"
                    className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                  />
                  <p className="text-xs text-orange-300 mt-1">补仓后基于新平均成本，默认-18%</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-orange-200">
                    最大持仓小时数 <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={buySurgeMaxHoldHours}
                    onChange={(e) => setBuySurgeMaxHoldHours(e.target.value)}
                    placeholder="例如: 72"
                    step="1"
                    min="1"
                    className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                  />
                  <p className="text-xs text-orange-300 mt-1">超过此时长强制平仓，默认72小时（3天）</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-orange-200">
                    等待超时时间 (小时) <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={buySurgeWaitTimeoutHours}
                    onChange={(e) => setBuySurgeWaitTimeoutHours(e.target.value)}
                    placeholder="例如: 48"
                    step="1"
                    min="1"
                    className="w-full px-4 py-2 bg-orange-800/50 border border-orange-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 text-white"
                  />
                  <p className="text-xs text-orange-300 mt-1">信号后未达到目标跌幅则放弃，默认48小时</p>
                </div>
              </div>
            )}

            {/* 策略说明 */}
            <div className="mt-4 pt-4 border-t border-orange-700">
              <h4 className="font-bold mb-2 text-orange-200">买量暴涨策略特点：</h4>
              <ul className="space-y-1 text-sm text-orange-200 list-disc list-inside">
                <li>信号识别：扫描所有USDT交易对，寻找当日主动买量 vs 昨日主动买量 ≥ 阈值（默认20倍）</li>
                <li>信号过滤：检查信号触发前1小时涨幅（5%≤涨幅≤48.5%）</li>
                <li>等待回调策略：根据买量倍数动态调整等待回调幅度（3%-6%）</li>
                <li>动态止盈：基于建仓后2小时的价格表现动态调整止盈阈值（20%-30%）</li>
                <li>补仓机制：价格下跌18%时补仓，重新计算平均成本</li>
                <li>快进快出：最大持仓72小时（3天）强制平仓</li>
              </ul>
            </div>
          </div>
        )}

        {/* 聪明钱策略参数设置 */}
        {backtestType === 'smartmoney' && (
          <div className="bg-purple-900/30 border border-purple-700 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-purple-300">聪明钱策略参数</h3>
              <button
                onClick={() => setShowSmartMoneyAdvanced(!showSmartMoneyAdvanced)}
                className="text-sm text-purple-400 hover:text-purple-300 transition-colors"
              >
                {showSmartMoneyAdvanced ? '收起 ▲' : '展开 ▼'}
              </button>
            </div>

            {/* 基础参数 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2 text-purple-200">
                  初始资金 (USDT) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={smartMoneyInitialCapital}
                  onChange={(e) => setSmartMoneyInitialCapital(e.target.value)}
                  placeholder="例如: 10000"
                  step="0.01"
                  min="0"
                  className="w-full px-4 py-2 bg-purple-800/50 border border-purple-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-purple-200">
                  基础仓位比例 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={smartMoneyPositionSizeRatio}
                  onChange={(e) => setSmartMoneyPositionSizeRatio(e.target.value)}
                  placeholder="例如: 10"
                  step="0.1"
                  min="0"
                  max="100"
                  className="w-full px-4 py-2 bg-purple-800/50 border border-purple-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
                />
                <p className="text-xs text-purple-300 mt-1">每次建仓金额占账户余额的百分比</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-purple-200">
                  最小涨幅 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={smartMoneyMinPctChg}
                  onChange={(e) => setSmartMoneyMinPctChg(e.target.value)}
                  placeholder="例如: 25"
                  step="0.1"
                  min="0"
                  className="w-full px-4 py-2 bg-purple-800/50 border border-purple-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
                />
                <p className="text-xs text-purple-300 mt-1">达到此涨幅才建仓</p>
              </div>
            </div>

            {/* 高级参数 */}
            {showSmartMoneyAdvanced && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-purple-700">
                <div>
                  <label className="flex items-center text-sm font-medium mb-2 text-purple-200">
                    <input
                      type="checkbox"
                      checked={enableDynamicLeverage}
                      onChange={(e) => setEnableDynamicLeverage(e.target.checked)}
                      className="mr-2 w-4 h-4"
                    />
                    启用动态杠杆策略
                  </label>
                  <p className="text-xs text-purple-300 ml-6">根据入场涨幅动态调整杠杆、止盈、止损</p>
                </div>

                <div>
                  <label className="flex items-center text-sm font-medium mb-2 text-purple-200">
                    <input
                      type="checkbox"
                      checked={enableLongTrade}
                      onChange={(e) => setEnableLongTrade(e.target.checked)}
                      className="mr-2 w-4 h-4"
                    />
                    允许做多
                  </label>
                  <p className="text-xs text-purple-300 ml-6">支持做多和做空两种交易方向</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-purple-200">
                    交易方向
                  </label>
                  <select
                    value={tradeDirection}
                    onChange={(e) => setTradeDirection(e.target.value as 'short' | 'long' | 'auto')}
                    className="w-full px-4 py-2 bg-purple-800/50 border border-purple-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
                  >
                    <option value="auto">自动（根据信号选择）</option>
                    <option value="short">只做空</option>
                    <option value="long">只做多</option>
                  </select>
                  <p className="text-xs text-purple-300 mt-1">选择交易方向：short=只做空, long=只做多, auto=自动</p>
                </div>

                <div>
                  <label className="flex items-center text-sm font-medium mb-2 text-purple-200">
                    <input
                      type="checkbox"
                      checked={enableVolumePositionSizing}
                      onChange={(e) => setEnableVolumePositionSizing(e.target.checked)}
                      className="mr-2 w-4 h-4"
                    />
                    启用成交额分级仓位
                  </label>
                  <p className="text-xs text-purple-300 ml-6">根据24h成交额动态调整仓位大小</p>
                </div>

                <div>
                  <label className="flex items-center text-sm font-medium mb-2 text-purple-200">
                    <input
                      type="checkbox"
                      checked={enableRiskControl}
                      onChange={(e) => setEnableRiskControl(e.target.checked)}
                      className="mr-2 w-4 h-4"
                    />
                    启用实盘风控检查
                  </label>
                  <p className="text-xs text-purple-300 ml-6">基于币安期货API获取实时市场情绪数据</p>
                </div>
              </div>
            )}

            {/* 策略说明 */}
            <div className="mt-4 pt-4 border-t border-purple-700">
              <h4 className="font-bold mb-2 text-purple-200">聪明钱策略特点：</h4>
              <ul className="space-y-1 text-sm text-purple-200 list-disc list-inside">
                <li>动态杠杆策略：根据入场涨幅动态调整杠杆、止盈、止损</li>
                <li>双向交易模式：支持做多和做空，根据巨鲸数据分析决定交易方向</li>
                <li>成交额分级仓位：根据24h成交额动态调整仓位大小</li>
                <li>入场等待机制：等待开盘价上涨一定幅度后再建仓，避免追高被套</li>
                <li>实盘风控系统：基于币安期货API获取实时市场情绪数据</li>
              </ul>
            </div>
          </div>
        )}

        {/* Backtrade4策略参数设置 */}
        {backtestType === 'backtrade4' && (
          <div className="bg-green-900/30 border border-green-700 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-green-300">Backtrade4策略参数</h3>
              <button
                onClick={() => setShowBacktrade4Advanced(!showBacktrade4Advanced)}
                className="text-sm text-green-400 hover:text-green-300 transition-colors"
              >
                {showBacktrade4Advanced ? '收起 ▲' : '展开 ▼'}
              </button>
            </div>

            {/* 基础参数 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2 text-green-200">
                  初始资金 (USDT) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={backtrade4InitialCapital}
                  onChange={(e) => setBacktrade4InitialCapital(e.target.value)}
                  placeholder="例如: 10000"
                  step="0.01"
                  min="0"
                  className="w-full px-4 py-2 bg-green-800/50 border border-green-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-green-200">
                  基础仓位比例 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={backtrade4PositionSizeRatio}
                  onChange={(e) => setBacktrade4PositionSizeRatio(e.target.value)}
                  placeholder="例如: 10"
                  step="0.1"
                  min="0"
                  max="100"
                  className="w-full px-4 py-2 bg-green-800/50 border border-green-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 text-white"
                />
                <p className="text-xs text-green-300 mt-1">每次建仓金额占账户余额的百分比</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-green-200">
                  最小涨幅 (%) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={backtrade4MinPctChg}
                  onChange={(e) => setBacktrade4MinPctChg(e.target.value)}
                  placeholder="例如: 25"
                  step="0.1"
                  min="0"
                  className="w-full px-4 py-2 bg-green-800/50 border border-green-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 text-white"
                />
                <p className="text-xs text-green-300 mt-1">达到此涨幅才建仓</p>
              </div>
            </div>

            {/* 高级参数 */}
            {showBacktrade4Advanced && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-green-700">
                <div>
                  <label className="flex items-center text-sm font-medium mb-2 text-green-200">
                    <input
                      type="checkbox"
                      checked={backtrade4EnableDynamicLeverage}
                      onChange={(e) => setBacktrade4EnableDynamicLeverage(e.target.checked)}
                      className="mr-2 w-4 h-4"
                    />
                    启用动态杠杆策略
                  </label>
                  <p className="text-xs text-green-300 ml-6">根据入场涨幅动态调整杠杆、止盈、止损、入场等待涨幅</p>
                </div>

                <div>
                  <label className="flex items-center text-sm font-medium mb-2 text-green-200">
                    <input
                      type="checkbox"
                      checked={backtrade4EnableLongTrade}
                      onChange={(e) => setBacktrade4EnableLongTrade(e.target.checked)}
                      className="mr-2 w-4 h-4"
                    />
                    允许做多
                  </label>
                  <p className="text-xs text-green-300 ml-6">支持做多和做空两种交易方向</p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-green-200">
                    交易方向
                  </label>
                  <select
                    value={backtrade4TradeDirection}
                    onChange={(e) => setBacktrade4TradeDirection(e.target.value as 'short' | 'long' | 'auto')}
                    className="w-full px-4 py-2 bg-green-800/50 border border-green-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 text-white"
                  >
                    <option value="auto">自动（根据信号选择）</option>
                    <option value="short">只做空</option>
                    <option value="long">只做多</option>
                  </select>
                  <p className="text-xs text-green-300 mt-1">选择交易方向：short=只做空, long=只做多, auto=自动</p>
                </div>

                <div>
                  <label className="flex items-center text-sm font-medium mb-2 text-green-200">
                    <input
                      type="checkbox"
                      checked={backtrade4EnableVolumePositionSizing}
                      onChange={(e) => setBacktrade4EnableVolumePositionSizing(e.target.checked)}
                      className="mr-2 w-4 h-4"
                    />
                    启用成交额分级仓位
                  </label>
                  <p className="text-xs text-green-300 ml-6">根据24h成交额动态调整仓位大小（0.5x-1.2x）</p>
                </div>

                <div>
                  <label className="flex items-center text-sm font-medium mb-2 text-green-200">
                    <input
                      type="checkbox"
                      checked={backtrade4EnableRiskControl}
                      onChange={(e) => setBacktrade4EnableRiskControl(e.target.checked)}
                      className="mr-2 w-4 h-4"
                    />
                    启用实盘风控检查
                  </label>
                  <p className="text-xs text-green-300 ml-6">基于币安期货API获取实时市场情绪数据（回测时跳过）</p>
                </div>
              </div>
            )}

            {/* 策略说明 */}
            <div className="mt-4 pt-4 border-t border-green-700">
              <h4 className="font-bold mb-2 text-green-200">Backtrade4策略特点：</h4>
              <ul className="space-y-1 text-sm text-green-200 list-disc list-inside">
                <li>动态杠杆策略：根据入场涨幅动态调整杠杆、止盈、止损、入场等待涨幅</li>
                <li>双向交易模式：支持做多和做空，根据巨鲸数据分析决定交易方向</li>
                <li>成交额分级仓位：根据24h成交额动态调整仓位大小（0.5x-1.2x）</li>
                <li>入场等待机制：等待开盘价上涨一定幅度后再建仓，避免追高被套</li>
                <li>逐小时检查：使用小时K线数据逐小时检查止盈止损条件</li>
                <li>实盘风控系统：基于币安期货API获取实时市场情绪数据（回测时跳过）</li>
                <li>60天均价风控：检查从60天平均价涨幅，避免主力获利不足继续拉升</li>
              </ul>
            </div>
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
              <div className={`grid grid-cols-2 ${result.long_trades !== undefined ? 'md:grid-cols-6' : result.max_drawdown !== undefined ? 'md:grid-cols-5' : 'md:grid-cols-4'} gap-4 text-sm`}>
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
                {result.max_drawdown !== undefined && (
                  <div>
                    <div className="text-gray-400">最大回撤</div>
                    <div className="text-xl font-bold text-yellow-400">{result.max_drawdown.toFixed(2)}%</div>
                  </div>
                )}
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

