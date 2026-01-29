import { useState, useEffect } from 'react'
import { API_URLS } from '../lib/api-config'

export default function LiveTradingDashboard() {
  const [balance, setBalance] = useState<number | null>(null)
  const [positions, setPositions] = useState<any[]>([])
  const [openOrders, setOpenOrders] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchAccountInfo = async () => {
    try {
      // setLoading(true) // 移除频繁刷新时的 loading 闪烁
      const [balanceRes, positionsRes, openOrdersRes] = await Promise.all([
        fetch(`${API_URLS.trade}/api/account/balance`),
        fetch(`${API_URLS.trade}/api/account/positions`),
        fetch(`${API_URLS.trade}/api/account/open-orders`)
      ])
      
      if (balanceRes.ok) {
        const data = await balanceRes.json()
        setBalance(data.available_balance)
      }
      
      if (positionsRes.ok) {
        const data = await positionsRes.json()
        setPositions(data)
      }

      if (openOrdersRes.ok) {
        const data = await openOrdersRes.json()
        setOpenOrders(data)
      }
    } catch (err) {
      console.error('获取账户信息失败:', err)
      // setError('无法连接到交易服务') // 暂不显示错误，以免网络波动影响体验
    }
  }

  useEffect(() => {
    fetchAccountInfo()
    const interval = setInterval(fetchAccountInfo, 3000) // 每3秒刷新
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-6">
      {/* 顶部状态栏 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 shadow-lg col-span-1 md:col-span-1">
          <div className="text-gray-400 text-xs mb-1">可用余额 (USDT)</div>
          <div className="text-2xl font-bold text-green-400 font-mono">
            {balance !== null ? `$${balance.toFixed(2)}` : '---'}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 shadow-lg col-span-1 md:col-span-1">
          <div className="text-gray-400 text-xs mb-1">持仓数量</div>
          <div className="text-2xl font-bold text-blue-400 font-mono">
            {positions.length}
          </div>
        </div>
         <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 shadow-lg col-span-1 md:col-span-2 flex items-center justify-between">
           <div>
             <div className="text-gray-400 text-xs mb-1">未实现盈亏 (估算)</div>
             <div className={`text-2xl font-bold font-mono ${
               positions.reduce((acc, p) => acc + parseFloat(p.unRealizedProfit), 0) >= 0 ? 'text-green-400' : 'text-red-400'
             }`}>
               ${positions.reduce((acc, p) => acc + parseFloat(p.unRealizedProfit), 0).toFixed(2)}
             </div>
           </div>
           <BotStatusIndicator />
         </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：下单面板 */}
        <div className="lg:col-span-1">
          <div className="bg-gray-800 rounded-lg shadow-lg border border-gray-700 overflow-hidden h-full">
            <div className="bg-gray-900/50 px-4 py-3 border-b border-gray-700 font-bold text-gray-200 flex items-center">
              <span className="mr-2">📝</span> 手动下单
            </div>
            <div className="p-4">
              <ManualTradeForm balance={balance} onOrderPlaced={fetchAccountInfo} />
            </div>
          </div>
        </div>

        {/* 中间：持仓列表 和 挂单列表 */}
        <div className="lg:col-span-2 flex flex-col space-y-6">
          {/* 持仓列表 */}
          <div className="bg-gray-800 rounded-lg shadow-lg border border-gray-700 overflow-hidden flex flex-col h-[300px]">
            <div className="bg-gray-900/50 px-4 py-3 border-b border-gray-700 font-bold text-gray-200 flex items-center justify-between">
              <div className="flex items-center"><span className="mr-2">📊</span> 持仓监控</div>
              <span className="text-xs text-gray-500 font-normal">每3秒刷新</span>
            </div>
            <div className="flex-1 overflow-auto">
              {positions.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-500 opacity-50">
                  <svg className="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                  <p>暂无持仓</p>
                </div>
              ) : (
                <table className="w-full text-sm text-left text-gray-300">
                  <thead className="bg-gray-700/50 text-gray-400 sticky top-0 backdrop-blur-sm z-10">
                    <tr>
                      <th className="px-4 py-3">交易对</th>
                      <th className="px-4 py-3 text-right">数量</th>
                      <th className="px-4 py-3 text-right">开仓价</th>
                      <th className="px-4 py-3 text-right">盈亏</th>
                      <th className="px-4 py-3 text-center">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {positions.map((pos) => {
                      const pnl = parseFloat(pos.unRealizedProfit)
                      const amt = parseFloat(pos.positionAmt)
                      const entryPrice = parseFloat(pos.entryPrice)
                      return (
                        <tr key={pos.symbol} className="hover:bg-gray-700/30 transition-colors">
                          <td className="px-4 py-3">
                            <div className="font-bold text-white">{pos.symbol}</div>
                            <div className={`text-xs ${amt > 0 ? 'text-green-500' : 'text-red-500'}`}>
                              {amt > 0 ? 'LONG' : 'SHORT'} {pos.leverage}x
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right font-mono">{Math.abs(amt)}</td>
                          <td className="px-4 py-3 text-right font-mono text-gray-400">{entryPrice > 0 ? entryPrice.toFixed(4) : '-'}</td>
                          <td className={`px-4 py-3 text-right font-mono font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {pnl > 0 ? '+' : ''}{pnl.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <ClosePositionButton symbol={pos.symbol} onClosed={fetchAccountInfo} />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* 挂单列表 */}
          <div className="bg-gray-800 rounded-lg shadow-lg border border-gray-700 overflow-hidden flex flex-col h-[300px]">
            <div className="bg-gray-900/50 px-4 py-3 border-b border-gray-700 font-bold text-gray-200 flex items-center justify-between">
              <div className="flex items-center"><span className="mr-2">📋</span> 当前挂单</div>
              <span className="text-xs text-gray-500 font-normal">每3秒刷新</span>
            </div>
            <div className="flex-1 overflow-auto">
              {openOrders.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-500 opacity-50">
                  <p>暂无挂单</p>
                </div>
              ) : (
                <table className="w-full text-sm text-left text-gray-300">
                  <thead className="bg-gray-700/50 text-gray-400 sticky top-0 backdrop-blur-sm z-10">
                    <tr>
                      <th className="px-4 py-3">交易对</th>
                      <th className="px-4 py-3">类型</th>
                      <th className="px-4 py-3 text-right">价格</th>
                      <th className="px-4 py-3 text-right">数量</th>
                      <th className="px-4 py-3 text-center">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {openOrders.map((order) => (
                      <tr key={order.orderId} className="hover:bg-gray-700/30 transition-colors">
                        <td className="px-4 py-3 font-medium">{order.symbol}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            order.side === 'BUY' ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                          }`}>
                            {order.side}
                          </span>
                          <span className="ml-2 text-xs text-gray-500">{order.type}</span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono">{parseFloat(order.price).toFixed(2)}</td>
                        <td className="px-4 py-3 text-right font-mono">{parseFloat(order.origQty)}</td>
                        <td className="px-4 py-3 text-center">
                          <CancelOrderButton symbol={order.symbol} orderId={order.orderId} onCancelled={fetchAccountInfo} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 底部：机器人日志 */}
      <div className="bg-gray-800 rounded-lg shadow-lg border border-gray-700 overflow-hidden">
        <BotControlPanel />
      </div>
    </div>
  )
}

function CancelOrderButton({ symbol, orderId, onCancelled }: { symbol: string, orderId: number, onCancelled: () => void }) {
  const [loading, setLoading] = useState(false)

  const handleCancel = async () => {
    if (!confirm(`确定要撤销 ${symbol} 的挂单吗？`)) return
    
    setLoading(true)
    try {
      const res = await fetch(`${API_URLS.trade}/api/trade/order?symbol=${symbol}&order_id=${orderId}`, {
        method: 'DELETE'
      })
      
      if (!res.ok) throw new Error('撤单失败')
      onCancelled()
    } catch (err) {
      alert(err instanceof Error ? err.message : '操作失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleCancel}
      disabled={loading}
      className="text-red-400 hover:text-red-300 disabled:opacity-50 text-xs underline"
    >
      {loading ? '撤单中...' : '撤销'}
    </button>
  )
}

function ClosePositionButton({ symbol, onClosed }: { symbol: string, onClosed: () => void }) {
  const [loading, setLoading] = useState(false)

  const handleClose = async () => {
    if (!confirm(`确定要市价全平 ${symbol} 吗？`)) return
    
    setLoading(true)
    try {
      const res = await fetch(`${API_URLS.trade}/api/trade/close-position`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol })
      })
      
      if (!res.ok) throw new Error('平仓失败')
      // alert('平仓成功') // 减少弹窗干扰
      onClosed()
    } catch (err) {
      alert(err instanceof Error ? err.message : '操作失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleClose}
      disabled={loading}
      className="px-3 py-1.5 bg-red-500/10 text-red-400 border border-red-500/30 rounded hover:bg-red-500/20 disabled:opacity-50 text-xs transition-all"
    >
      {loading ? '...' : '平仓'}
    </button>
  )
}

function ManualTradeForm({ balance, onOrderPlaced }: { balance: number | null, onOrderPlaced: () => void }) {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [side, setSide] = useState('BUY')
  const [orderType, setOrderType] = useState('MARKET')
  const [price, setPrice] = useState('')
  const [amount, setAmount] = useState('')
  const [amountType, setAmountType] = useState<'quantity' | 'usdt'>('usdt') // 默认 USDT
  const [loading, setLoading] = useState(false)

  // 快捷比例选择
  const setPercentage = (pct: number) => {
    if (balance && amountType === 'usdt') {
      setAmount((balance * pct).toFixed(2))
    } else {
      alert('请先切换到 USDT 模式并确保已连接账户')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      let quantity = parseFloat(amount)
      let finalPrice = price ? parseFloat(price) : undefined
      
      // 如果是 USDT 模式，需要估算数量
      if (amountType === 'usdt') {
        // 这里需要当前价格来计算数量。
        // 由于没有实时价格流，我们暂时只能用用户输入的限价，或者是"大概"估算。
        // 为了严谨，如果是市价单且用USDT，后端其实需要支持 quoteOrderQty。
        // 但我们的后端只支持 quantity (币数)。
        // 临时方案：如果是限价单，用 price 计算；如果是市价单，暂时不支持 USDT 输入或者需要先查询价格。
        // 简化起见：提示用户切换或者在前端做一个简单的价格查询 (如果有行情API)。
        
        // 尝试获取一次当前价格
        if (orderType === 'MARKET') {
           // 理想情况是调用后端获取价格，这里简化处理：
           // 如果是市价单，提示用户输入币数量，或者我们需要先 fetch ticker
           const tickerRes = await fetch(`${API_URLS.data}/api/ticker/price?symbol=${symbol}`)
           if (tickerRes.ok) {
             const ticker = await tickerRes.json()
             const currentPrice = parseFloat(ticker.price)
             quantity = quantity / currentPrice
           } else {
             throw new Error('无法获取当前价格来计算数量，请切换到"币数"模式')
           }
        } else {
           if (!finalPrice) throw new Error('限价单请输入价格')
           quantity = quantity / finalPrice
        }
      }

      const res = await fetch(`${API_URLS.trade}/api/trade/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: symbol.toUpperCase(),
          side,
          order_type: orderType,
          quantity,
          price: finalPrice
        })
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '下单失败')
      }

      alert('下单成功')
      setAmount('')
      onOrderPlaced()
    } catch (err) {
      alert(err instanceof Error ? err.message : '下单失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* 交易对 */}
      <div>
        <label className="block text-gray-500 text-xs mb-1 uppercase">Symbol</label>
        <div className="relative">
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white font-mono focus:border-blue-500 focus:outline-none"
            placeholder="BTCUSDT"
          />
        </div>
      </div>

      {/* 方向选择 */}
      <div className="grid grid-cols-2 gap-2 bg-gray-700 p-1 rounded">
        <button
          type="button"
          onClick={() => setSide('BUY')}
          className={`py-1.5 rounded text-sm font-bold transition-all ${
            side === 'BUY' 
              ? 'bg-green-600 text-white shadow' 
              : 'text-gray-400 hover:text-white'
          }`}
        >
          做多 (Long)
        </button>
        <button
          type="button"
          onClick={() => setSide('SELL')}
          className={`py-1.5 rounded text-sm font-bold transition-all ${
            side === 'SELL' 
              ? 'bg-red-600 text-white shadow' 
              : 'text-gray-400 hover:text-white'
          }`}
        >
          做空 (Short)
        </button>
      </div>

      {/* 订单类型 */}
      <div className="flex space-x-4 text-sm">
        <label className="flex items-center space-x-2 cursor-pointer">
          <input 
            type="radio" 
            name="orderType" 
            checked={orderType === 'MARKET'} 
            onChange={() => setOrderType('MARKET')}
            className="text-blue-500 focus:ring-blue-500 bg-gray-700 border-gray-600"
          />
          <span className="text-gray-300">市价单</span>
        </label>
        <label className="flex items-center space-x-2 cursor-pointer">
          <input 
            type="radio" 
            name="orderType" 
            checked={orderType === 'LIMIT'} 
            onChange={() => setOrderType('LIMIT')}
            className="text-blue-500 focus:ring-blue-500 bg-gray-700 border-gray-600"
          />
          <span className="text-gray-300">限价单</span>
        </label>
      </div>

      {/* 价格输入 (仅限价单) */}
      {orderType === 'LIMIT' && (
        <div className="animate-fade-in">
          <label className="block text-gray-500 text-xs mb-1">价格 (USDT)</label>
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white font-mono focus:border-blue-500 focus:outline-none"
            placeholder="输入价格"
            step="0.01"
            required
          />
        </div>
      )}

      {/* 数量输入 */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <label className="text-gray-500 text-xs">数量</label>
          <div className="flex text-xs bg-gray-700 rounded overflow-hidden">
            <button
              type="button"
              onClick={() => setAmountType('usdt')}
              className={`px-2 py-0.5 ${amountType === 'usdt' ? 'bg-blue-600 text-white' : 'text-gray-400'}`}
            >
              USDT
            </button>
            <button
              type="button"
              onClick={() => setAmountType('quantity')}
              className={`px-2 py-0.5 ${amountType === 'quantity' ? 'bg-blue-600 text-white' : 'text-gray-400'}`}
            >
              币
            </button>
          </div>
        </div>
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white font-mono focus:border-blue-500 focus:outline-none"
          placeholder={amountType === 'usdt' ? "输入金额 (USDT)" : "输入数量 (个)"}
          step="0.0001"
          required
        />
        
        {/* 快捷比例 */}
        {amountType === 'usdt' && (
          <div className="grid grid-cols-4 gap-2 mt-2">
            {[0.1, 0.25, 0.5, 1.0].map((pct) => (
              <button
                key={pct}
                type="button"
                onClick={() => setPercentage(pct)}
                className="bg-gray-700 hover:bg-gray-600 text-gray-400 text-xs py-1 rounded transition-colors"
              >
                {pct * 100}%
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={loading}
        className={`w-full py-3 rounded font-bold text-white transition-all transform active:scale-95 ${
          side === 'BUY' 
            ? 'bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 shadow-lg shadow-green-900/50' 
            : 'bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 shadow-lg shadow-red-900/50'
        } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        {loading ? '提交中...' : `${side === 'BUY' ? '买入' : '卖出'} ${symbol}`}
      </button>
    </form>
  )
}

function BotStatusIndicator() {
  const [status, setStatus] = useState<any>(null)
  
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_URLS.trade}/api/bot/status`)
        if (res.ok) setStatus(await res.json())
      } catch (e) {}
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex items-center space-x-2 bg-black/20 px-3 py-1.5 rounded-full">
      <div className={`w-2 h-2 rounded-full ${status?.is_running ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
      <span className={`text-xs font-bold ${status?.is_running ? 'text-green-400' : 'text-gray-400'}`}>
        BOT: {status?.is_running ? 'ON' : 'OFF'}
      </span>
    </div>
  )
}

function BotControlPanel() {
  const [status, setStatus] = useState<any>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URLS.trade}/api/bot/status`)
      if (res.ok) setStatus(await res.json())
    } catch (err) {
      console.error(err)
    }
  }

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${API_URLS.trade}/api/bot/logs?limit=50`)
      if (res.ok) {
        const data = await res.json()
        setLogs(data.logs)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const toggleBot = async (action: 'start' | 'stop') => {
    if (!confirm(`确定要${action === 'start' ? '启动' : '停止'}机器人吗？`)) return
    
    setLoading(true)
    try {
      const res = await fetch(`${API_URLS.trade}/api/bot/${action}`, { method: 'POST' })
      if (!res.ok) throw new Error('操作失败')
      await fetchStatus()
    } catch (err) {
      alert(err instanceof Error ? err.message : '操作失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    fetchLogs()
    const interval = setInterval(() => {
      fetchStatus()
      fetchLogs()
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex flex-col md:flex-row h-full">
      <div className="p-4 bg-gray-900/50 border-r border-gray-700 w-full md:w-64 flex flex-col justify-between">
        <div>
          <div className="text-gray-400 text-xs mb-2 uppercase tracking-wider">机器人控制</div>
          <button
            onClick={() => toggleBot(status?.is_running ? 'stop' : 'start')}
            disabled={loading}
            className={`w-full py-3 rounded-lg font-bold text-white transition-all shadow-lg mb-4 ${
              status?.is_running 
                ? 'bg-red-600 hover:bg-red-700 shadow-red-900/20' 
                : 'bg-green-600 hover:bg-green-700 shadow-green-900/20'
            } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? '...' : (status?.is_running ? '停止运行' : '启动运行')}
          </button>
          
          {status?.config && (
            <div className="space-y-2 text-xs text-gray-500">
              <div className="flex justify-between"><span>杠杆倍数:</span> <span className="text-gray-300">{status.config.leverage}x</span></div>
              <div className="flex justify-between"><span>单笔仓位:</span> <span className="text-gray-300">{(status.config.position_size_ratio * 100).toFixed(0)}%</span></div>
              <div className="flex justify-between"><span>最大持仓:</span> <span className="text-gray-300">{status.config.max_positions}</span></div>
            </div>
          )}
        </div>
        <div className="text-[10px] text-gray-600 mt-4">
          上次扫描: {status?.last_scan_hour ? `${status.last_scan_hour}:02` : '无'}
        </div>
      </div>

      <div className="flex-1 bg-black/40 p-4 font-mono text-xs overflow-hidden flex flex-col">
        <div className="text-gray-500 mb-2 flex justify-between">
          <span>运行日志</span>
          <span className="text-gray-600">Auto-scroll enabled</span>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1 pr-2 custom-scrollbar">
          {logs.length === 0 ? (
            <div className="text-gray-700 italic">暂无日志...</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className={`border-l-2 pl-2 ${
                log.includes('ERROR') ? 'border-red-500 text-red-400' :
                log.includes('WARNING') ? 'border-yellow-500 text-yellow-400' :
                log.includes('开仓') ? 'border-green-500 text-green-300' :
                log.includes('平仓') ? 'border-blue-500 text-blue-300' :
                'border-gray-700 text-gray-400'
              }`}>
                {log}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
