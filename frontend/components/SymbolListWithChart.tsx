'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi } from 'lightweight-charts'
import { API_URLS } from '../lib/api-config'

const API_BASE_URL = API_URLS.data

interface KlineData {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  pct_chg?: number
}

export default function SymbolListWithChart() {
  // 交易对列表相关状态
  const [interval, setInterval] = useState('1d')
  const [symbols, setSymbols] = useState<string[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [loadingSymbols, setLoadingSymbols] = useState(false)
  const [symbolsError, setSymbolsError] = useState<string | null>(null)
  const [searchKeyword, setSearchKeyword] = useState('')

  // 图表相关状态
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const [loadingChart, setLoadingChart] = useState(false)
  const [chartError, setChartError] = useState<string | null>(null)
  const [dataCount, setDataCount] = useState(0)
  const [totalDataCount, setTotalDataCount] = useState(0)
  const [loadingMoreData, setLoadingMoreData] = useState(false)

  // 日期筛选
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // 用于滚动到选中交易对的 ref
  const symbolItemRefs = useRef<{ [key: string]: HTMLDivElement | null }>({})
  const listContainerRef = useRef<HTMLDivElement | null>(null)

  // 获取交易对列表
  const fetchSymbols = async () => {
    setLoadingSymbols(true)
    setSymbolsError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/symbols?interval=${interval}`)
      
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
      
      const data = await response.json()
      const symbolList = data.symbols || []
      setSymbols(symbolList)
      
      // 如果有交易对且没有选中，自动选中第一个
      if (symbolList.length > 0 && !selectedSymbol) {
        setSelectedSymbol(symbolList[0])
      }
    } catch (err: any) {
      console.error('获取交易对列表错误:', err)
      let errorMessage = '请求失败'
      
      if (err.message) {
        errorMessage = err.message
      } else if (err.name === 'TypeError' && err.message.includes('fetch')) {
        errorMessage = `无法连接到后端服务器 (${API_BASE_URL})。请确保后端服务已启动。`
      } else {
        errorMessage = `请求失败: ${err.toString()}`
      }
      
      setSymbolsError(errorMessage)
    } finally {
      setLoadingSymbols(false)
    }
  }

  // 获取K线数据（支持分段加载）
  const fetchKlineData = useCallback(async (
    symbol: string, 
    limit?: number, 
    offset?: number
  ): Promise<{ klineData: KlineData[], totalCount: number } | null> => {
    if (!symbol) return null

    try {
      let url = `${API_BASE_URL}/api/kline/${interval}/${symbol}`
      const params = new URLSearchParams()
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)
      if (limit) params.append('limit', limit.toString())
      if (offset !== undefined) params.append('offset', offset.toString())
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
      const klineData: KlineData[] = result.data || []
      const totalCount = result.total_count || klineData.length
      
      return { klineData, totalCount }
    } catch (err: any) {
      console.error('获取K线数据错误:', err)
      let errorMessage = '请求失败'
      
      if (err.message) {
        errorMessage = err.message
      } else if (err.name === 'TypeError' && err.message.includes('fetch')) {
        errorMessage = `无法连接到后端服务器 (${API_BASE_URL})。请确保后端服务已启动。`
      } else {
        errorMessage = `请求失败: ${err.toString()}`
      }
      
      setChartError(errorMessage)
      return null
    }
  }, [interval, startDate, endDate])

  // 解析时间字符串为Unix时间戳（秒）
  const parseTime = useCallback((timeStr: string): number => {
    try {
      // 如果是日期格式 YYYY-MM-DD
      if (timeStr.length === 10) {
        const date = new Date(timeStr + 'T00:00:00Z')
        return Math.floor(date.getTime() / 1000)
      }
      // 如果是完整时间格式 YYYY-MM-DD HH:MM:SS
      const date = new Date(timeStr)
      return Math.floor(date.getTime() / 1000)
    } catch (e) {
      console.error('时间解析错误:', timeStr, e)
      return 0
    }
  }, [])

  // 转换K线数据为图表格式（确保按时间升序排序并去重）
  const convertToChartData = useCallback((klineData: KlineData[]) => {
    // 先按时间排序（升序）
    const sortedData = [...klineData].sort((a, b) => {
      const timeA = parseTime(a.trade_date)
      const timeB = parseTime(b.trade_date)
      return timeA - timeB
    })

    // 使用 Map 去重（基于时间戳）
    const candlestickMap = new Map<number, any>()
    const volumeMap = new Map<number, any>()

    sortedData.forEach((item) => {
      const time = parseTime(item.trade_date)
      if (time === 0) return
      
      // 如果时间戳已存在，跳过（保留第一个）
      if (!candlestickMap.has(time)) {
        candlestickMap.set(time, {
          time: time as any,
          open: parseFloat(item.open.toString()),
          high: parseFloat(item.high.toString()),
          low: parseFloat(item.low.toString()),
          close: parseFloat(item.close.toString()),
        })
      }
      
      if (!volumeMap.has(time)) {
        const isUp = parseFloat(item.close.toString()) >= parseFloat(item.open.toString())
        volumeMap.set(time, {
          time: time as any,
          value: parseFloat(item.volume.toString()),
          color: isUp ? '#26a69a' : '#ef5350',
        })
      }
    })

    // 转换为数组（已经按时间排序）
    const candlestickData = Array.from(candlestickMap.values())
    const volumeData = Array.from(volumeMap.values())

    return { candlestickData, volumeData }
  }, [parseTime])

  // 更新图表数据
  const updateChartData = useCallback((
    candlestickData: any[], 
    volumeData: any[], 
    isInitialLoad: boolean = false
  ) => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current) {
      console.warn('图表系列未初始化')
      return false
    }

    try {
      if (isInitialLoad) {
        // 初始加载：设置数据
        candlestickSeriesRef.current.setData(candlestickData as any)
        volumeSeriesRef.current.setData(volumeData as any)
      } else {
        // 追加数据：使用update方法追加
        candlestickData.forEach(item => {
          candlestickSeriesRef.current?.update(item)
        })
        volumeData.forEach(item => {
          volumeSeriesRef.current?.update(item)
        })
      }

      // 设置初始视图显示最新的100根K线
      if (chartRef.current && isInitialLoad) {
        const MAX_DISPLAY_BARS = 100
        const timeScale = chartRef.current.timeScale()
        if (candlestickData.length > MAX_DISPLAY_BARS) {
          const latestTime = candlestickData[candlestickData.length - 1]?.time
          if (latestTime) {
            // 计算时间间隔（根据间隔类型）
            let timeInterval = 86400 // 默认日线
            if (interval.includes('h')) {
              const hours = parseInt(interval.replace('h', '')) || 1
              timeInterval = hours * 3600
            } else if (interval.includes('m')) {
              const minutes = parseInt(interval.replace('m', '')) || 1
              timeInterval = minutes * 60
            }
            const fromTime = (latestTime as number) - (MAX_DISPLAY_BARS - 1) * timeInterval
            timeScale.setVisibleRange({
              from: fromTime as any,
              to: latestTime as any,
            })
          }
        } else {
          timeScale.fitContent()
        }
      }
      
      return true
    } catch (err) {
      console.error('更新图表数据失败:', err)
      setChartError('更新图表数据失败: ' + (err instanceof Error ? err.message : String(err)))
      return false
    }
  }, [interval])

  // 加载初始数据并显示图表
  const loadInitialDataAndDisplay = useCallback(async (symbol: string) => {
    const INITIAL_LIMIT = 500
    const LARGE_DATA_THRESHOLD = 1500

    setLoadingChart(true)
    setChartError(null)

    // 先获取初始的500条数据
    const result = await fetchKlineData(symbol, INITIAL_LIMIT)
    if (!result) {
      setLoadingChart(false)
      return
    }

    const { klineData: initialData, totalCount } = result
    setTotalDataCount(totalCount)
    setDataCount(initialData.length)

    // 转换数据格式
    const { candlestickData, volumeData } = convertToChartData(initialData)

    // 等待图表初始化
    const waitForChart = () => {
      return new Promise<boolean>((resolve) => {
        let attempts = 0
        const maxAttempts = 20 // 最多等待2秒
        
        const checkChart = () => {
          if (candlestickSeriesRef.current && volumeSeriesRef.current) {
            resolve(true)
          } else if (attempts < maxAttempts) {
            attempts++
            setTimeout(checkChart, 100)
          } else {
            resolve(false)
          }
        }
        
        checkChart()
      })
    }

    const chartReady = await waitForChart()
    if (!chartReady) {
      setChartError('图表初始化超时')
      setLoadingChart(false)
      return
    }

    // 更新图表数据
    const success = updateChartData(candlestickData, volumeData, true)
    setLoadingChart(false)

    if (!success) return

    // 如果数据量很大，在图表显示完成后加载剩余数据
    if (totalCount > LARGE_DATA_THRESHOLD) {
      console.log(`数据量较大(${totalCount}条)，将在图表显示完成后加载剩余数据...`)
      
      // 等待图表渲染完成（延迟1秒确保图表已显示）
      setTimeout(async () => {
        setLoadingMoreData(true)
        
        // 分段加载剩余数据
        const remainingCount = totalCount - INITIAL_LIMIT
        const batchSize = 1000 // 每次加载1000条
        
        for (let offset = INITIAL_LIMIT; offset < totalCount; offset += batchSize) {
          const limit = Math.min(batchSize, totalCount - offset)
          const moreResult = await fetchKlineData(symbol, limit, offset)
          
          if (moreResult && moreResult.klineData.length > 0) {
            const { candlestickData: moreCandlestickData, volumeData: moreVolumeData } = 
              convertToChartData(moreResult.klineData)
            
            // 追加数据到图表（需要按时间排序后追加并去重）
            // 注意：由于我们是从后往前取数据，需要合并并排序
            const currentCandlestickData = candlestickSeriesRef.current?.data() || []
            const currentVolumeData = volumeSeriesRef.current?.data() || []
            
            // 使用 Map 去重（基于时间戳）
            const candlestickMap = new Map<number, any>()
            const volumeMap = new Map<number, any>()
            
            // 先添加现有数据
            currentCandlestickData.forEach(item => {
              const time = item.time as number
              if (!candlestickMap.has(time)) {
                candlestickMap.set(time, item)
              }
            })
            currentVolumeData.forEach(item => {
              const time = item.time as number
              if (!volumeMap.has(time)) {
                volumeMap.set(time, item)
              }
            })
            
            // 再添加新数据（如果有重复时间戳，新数据会覆盖旧数据）
            moreCandlestickData.forEach(item => {
              const time = item.time as number
              candlestickMap.set(time, item)
            })
            moreVolumeData.forEach(item => {
              const time = item.time as number
              volumeMap.set(time, item)
            })
            
            // 转换为数组并按时间升序排序
            const mergedCandlestick = Array.from(candlestickMap.values())
              .sort((a, b) => {
                const timeA = a.time as number
                const timeB = b.time as number
                return timeA - timeB
              })
            const mergedVolume = Array.from(volumeMap.values())
              .sort((a, b) => {
                const timeA = a.time as number
                const timeB = b.time as number
                return timeA - timeB
              })
            
            // 重新设置所有数据（确保按时间升序且无重复）
            candlestickSeriesRef.current?.setData(mergedCandlestick as any)
            volumeSeriesRef.current?.setData(mergedVolume as any)
            
            setDataCount(mergedCandlestick.length)
            
            console.log(`已加载 ${Math.min(offset + limit, totalCount)}/${totalCount} 条数据`)
            
            // 添加小延迟避免请求过快
            await new Promise(resolve => setTimeout(resolve, 100))
          }
        }
        
        setLoadingMoreData(false)
        console.log(`所有数据加载完成，共 ${totalCount} 条`)
      }, 1000)
    } else {
      // 数据量不大，直接加载全部
      const fullResult = await fetchKlineData(symbol)
      if (fullResult) {
        const { klineData: allData, totalCount: finalTotalCount } = fullResult
        setTotalDataCount(finalTotalCount)
        setDataCount(allData.length)
        
        const { candlestickData: allCandlestickData, volumeData: allVolumeData } = 
          convertToChartData(allData)
        
        updateChartData(allCandlestickData, allVolumeData, true)
      }
    }
  }, [fetchKlineData, convertToChartData, updateChartData])


  // 初始化图表
  useEffect(() => {
    if (!chartContainerRef.current) return

    // 等待容器有尺寸后再初始化
    const initChart = () => {
      if (!chartContainerRef.current) return
      
      const container = chartContainerRef.current
      const width = container.clientWidth || 800
      const height = container.clientHeight || 500

      if (width === 0 || height === 0) {
        // 如果容器还没有尺寸，延迟初始化
        setTimeout(initChart, 100)
        return
      }

      const chart = createChart(container, {
        layout: {
          background: { type: ColorType.Solid, color: '#1e1e1e' },
          textColor: '#d1d5db',
        },
        grid: {
          vertLines: { color: '#2a2a2a' },
          horzLines: { color: '#2a2a2a' },
        },
        width: width,
        height: height,
        timeScale: {
          timeVisible: true,
          secondsVisible: true,
          borderColor: '#485563',
          rightOffset: 10,
          barSpacing: 3,
        },
        rightPriceScale: {
          borderColor: '#485563',
        },
        localization: {
          timeFormatter: (businessDayOrTimestamp: number) => {
            const date = new Date(businessDayOrTimestamp * 1000)
            const year = date.getFullYear()
            const month = String(date.getMonth() + 1).padStart(2, '0')
            const day = String(date.getDate()).padStart(2, '0')
            const hours = String(date.getHours()).padStart(2, '0')
            const minutes = String(date.getMinutes()).padStart(2, '0')
            const seconds = String(date.getSeconds()).padStart(2, '0')
            return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
          },
        },
      })

      chartRef.current = chart

      // 创建K线系列
      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
      })
      candlestickSeriesRef.current = candlestickSeries

      // 创建成交量系列
      const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '',
      })
      volumeSeriesRef.current = volumeSeries
      
      // 设置成交量价格轴的边距
      chart.priceScale('').applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      })
    }

    initChart()

    // 响应式调整
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        const container = chartContainerRef.current
        const width = container.clientWidth
        const height = container.clientHeight
        if (width > 0 && height > 0) {
          chartRef.current.applyOptions({
            width: width,
            height: height,
          })
        }
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
        candlestickSeriesRef.current = null
        volumeSeriesRef.current = null
      }
    }
  }, [])

  // 当选中交易对或间隔改变时，加载数据
  useEffect(() => {
    if (selectedSymbol) {
      loadInitialDataAndDisplay(selectedSymbol)
    }
  }, [selectedSymbol, interval, startDate, endDate, loadInitialDataAndDisplay])

  // 当选中交易对改变时，滚动到对应位置
  useEffect(() => {
    if (selectedSymbol && symbolItemRefs.current[selectedSymbol]) {
      // 延迟一下确保DOM已更新
      setTimeout(() => {
        symbolItemRefs.current[selectedSymbol]?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        })
      }, 100)
    }
  }, [selectedSymbol])

  // 初始加载交易对列表
  useEffect(() => {
    fetchSymbols()
  }, [interval])

  // 当间隔改变时，重新加载交易对列表
  useEffect(() => {
    fetchSymbols()
  }, [interval])

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

  return (
    <div className="h-full flex flex-col">
      {/* 顶部控制栏 */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-semibold">交易对与K线图表</h2>
        <div className="flex items-center space-x-4">
          <div>
            <label className="block text-sm font-medium mb-1">K线间隔</label>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {INTERVALS.map((int) => (
                <option key={int.value} value={int.value}>
                  {int.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">开始日期</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">结束日期</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={fetchSymbols}
            disabled={loadingSymbols}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 mt-6"
          >
            {loadingSymbols ? '加载中...' : '刷新列表'}
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {(symbolsError || chartError) && (
        <div className="mb-4 p-4 bg-red-500/20 text-red-400 border border-red-500/50 rounded-lg">
          {symbolsError || chartError}
        </div>
      )}

      {/* 主要内容区域：左右分栏 */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* 左侧：交易对列表 */}
        <div className="w-64 flex-shrink-0 flex flex-col bg-gray-700/50 rounded-lg p-4">
          <div className="mb-4">
            <h3 className="text-lg font-semibold mb-2">交易对列表</h3>
            {/* 搜索框 */}
            <div className="mb-3">
              <input
                type="text"
                placeholder="搜索交易对..."
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white placeholder-gray-500"
              />
            </div>
            {loadingSymbols ? (
              <div className="text-sm text-gray-400">加载中...</div>
            ) : (
              <div className="text-sm text-gray-400">
                共 {symbols.length} 个交易对
                {searchKeyword && (
                  <span className="ml-1">
                    （匹配 {symbols.filter(s => s.toLowerCase().includes(searchKeyword.toLowerCase())).length} 个）
                  </span>
                )}
              </div>
            )}
          </div>
          
          {/* 可滚动的列表 */}
          <div 
            ref={listContainerRef}
            className="flex-1 overflow-y-auto"
          >
            {loadingSymbols && symbols.length === 0 ? (
              <div className="text-center py-8 text-gray-400">加载中...</div>
            ) : symbols.length === 0 ? (
              <div className="text-center py-8 text-gray-400">暂无数据</div>
            ) : (() => {
              // 根据搜索关键词过滤交易对
              const filteredSymbols = searchKeyword
                ? symbols.filter(s => s.toLowerCase().includes(searchKeyword.toLowerCase()))
                : symbols
              
              if (filteredSymbols.length === 0 && searchKeyword) {
                return (
                  <div className="text-center py-8 text-gray-400">
                    未找到匹配的交易对
                  </div>
                )
              }
              
              return (
                <div className="space-y-2">
                  {filteredSymbols.map((symbol) => {
                    return (
                      <div
                        key={symbol}
                        ref={(el) => {
                          symbolItemRefs.current[symbol] = el
                        }}
                        onClick={() => {
                          setSelectedSymbol(symbol)
                          setSearchKeyword('') // 选择后清空搜索框
                        }}
                        className={`px-4 py-3 rounded-lg cursor-pointer transition-all ${
                          selectedSymbol === symbol
                            ? 'bg-blue-600 text-white shadow-lg ring-2 ring-blue-400'
                            : 'bg-gray-600/50 hover:bg-gray-600 text-gray-200'
                        }`}
                      >
                        <div className="font-medium">
                          {symbol}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )
            })()}
          </div>
        </div>

        {/* 右侧：K线图表 */}
        <div className="flex-1 flex flex-col bg-gray-700/50 rounded-lg p-4 min-w-0">
          <div className="mb-4">
            <h3 className="text-lg font-semibold mb-2">
              K线图表
              {selectedSymbol && (
                <span className="ml-2 text-blue-400">{selectedSymbol}</span>
              )}
            </h3>
            {totalDataCount > 0 && (
              <div className="text-sm text-gray-400">
                共 {totalDataCount} 条数据，已加载 {dataCount} 条
                {loadingMoreData && (
                  <span className="ml-2 text-blue-400">（正在加载剩余数据...）</span>
                )}
                {totalDataCount > 1500 && dataCount < totalDataCount && !loadingMoreData && (
                  <span className="ml-2 text-yellow-400">（初始显示500条，其余数据已自动加载）</span>
                )}
              </div>
            )}
            {loadingChart && (
              <div className="text-sm text-blue-400">加载中...</div>
            )}
          </div>

          {/* 图表容器始终存在，确保图表能正确初始化 */}
          <div className="flex-1 min-h-0 relative" style={{ minHeight: '400px' }}>
            {!selectedSymbol ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-gray-400">请从左侧选择一个交易对</div>
              </div>
            ) : loadingChart ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-gray-400">加载图表数据中...</div>
              </div>
            ) : null}
            {/* 图表容器始终渲染，但可能被覆盖 */}
            <div 
              ref={chartContainerRef} 
              className="w-full h-full" 
              style={{ 
                minHeight: '400px',
                visibility: (!selectedSymbol || loadingChart) ? 'hidden' : 'visible'
              }} 
            />
          </div>
        </div>
      </div>
    </div>
  )
}

