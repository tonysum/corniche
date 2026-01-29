'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { API_URLS } from '../lib/api-config'

interface TopGainer {
  symbol: string
  pct_chg: number
  close: number | null
  open: number | null
  high: number | null
  low: number | null
  volume: number | null
}

interface TopGainersContextType {
  topGainers: TopGainer[]
  topGainersDate: string
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const TopGainersContext = createContext<TopGainersContextType | undefined>(undefined)

export function TopGainersProvider({ children }: { children: ReactNode }) {
  const [topGainers, setTopGainers] = useState<TopGainer[]>([])
  const [topGainersDate, setTopGainersDate] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTopGainers = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const apiUrl = `${API_URLS.data}/api/top-gainers?top_n=3`
      console.log('正在获取涨幅排名:', apiUrl)
      
      // 创建超时控制器
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10000) // 10秒超时
      
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      })
      
      clearTimeout(timeoutId)
      
      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`获取涨幅排名失败: ${response.status} ${response.statusText} - ${errorText}`)
      }
      
      const data = await response.json()
      console.log('前一天涨幅排名数据:', data)
      
      // 如果返回了 message，说明有特殊提示（比如未找到数据）
      if (data.message) {
        console.warn('API 返回提示:', data.message)
      }
      
      setTopGainers(data.top_gainers || [])
      setTopGainersDate(data.date || '')
      
      // 如果没有数据，记录详细信息用于调试
      if (!data.top_gainers || data.top_gainers.length === 0) {
        console.warn('未获取到前一天涨幅数据:', {
          date: data.date,
          message: data.message,
          total_count: data.total_count
        })
      }
    } catch (err) {
      // 如果是连接错误，降级为警告，避免控制台刷屏
      const isConnectionError = err instanceof TypeError && err.message.includes('Failed to fetch')
      
      if (isConnectionError) {
        console.warn(`无法连接到数据服务 (${API_URLS.data})，涨幅榜功能暂不可用`)
      } else {
        console.error('获取涨幅排名失败:', err)
      }
      
      // 更友好的错误信息
      let errorMessage = '获取涨幅排名失败'
      if (isConnectionError) {
        errorMessage = `数据服务暂不可用`
      } else if (err instanceof Error) {
        if (err.name === 'AbortError' || err.message.includes('timeout') || err.message.includes('aborted')) {
          errorMessage = '请求超时'
        } else {
          errorMessage = err.message
        }
      }
      
      setError(errorMessage)
      setTopGainers([])
    } finally {
      setLoading(false)
    }
  }

  // 应用启动时加载数据
  useEffect(() => {
    fetchTopGainers()
  }, [])

  return (
    <TopGainersContext.Provider
      value={{
        topGainers,
        topGainersDate,
        loading,
        error,
        refresh: fetchTopGainers,
      }}
    >
      {children}
    </TopGainersContext.Provider>
  )
}

export function useTopGainers() {
  const context = useContext(TopGainersContext)
  if (context === undefined) {
    throw new Error('useTopGainers must be used within a TopGainersProvider')
  }
  return context
}

