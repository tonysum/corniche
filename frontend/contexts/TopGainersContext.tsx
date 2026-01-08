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
      const response = await fetch(`${API_URLS.data}/api/top-gainers?top_n=3`)
      if (!response.ok) {
        throw new Error('获取涨幅排名失败')
      }
      const data = await response.json()
      setTopGainers(data.top_gainers || [])
      setTopGainersDate(data.date || '')
    } catch (err) {
      console.error('获取涨幅排名失败:', err)
      setError(err instanceof Error ? err.message : '获取涨幅排名失败')
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

