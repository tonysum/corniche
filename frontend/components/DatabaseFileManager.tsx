'use client'

import { useState } from 'react'
import { API_URLS } from '../lib/api-config'

const API_BASE_URL = API_URLS.data

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

export default function DatabaseFileManager() {
  const [downloadingDb, setDownloadingDb] = useState(false)
  const [uploadingDb, setUploadingDb] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [autoUpdating, setAutoUpdating] = useState(false)
  const [selectedInterval, setSelectedInterval] = useState('1d')

  const handleDownloadDatabase = async () => {
    setDownloadingDb(true)
    setMessage(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/download-database`, {
        method: 'GET',
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '下载失败' }))
        throw new Error(errorData.detail || '下载数据库文件失败')
      }

      // 获取文件名（从响应头或生成）
      const contentDisposition = response.headers.get('Content-Disposition')
      let filename = 'crypto_data.db'
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }

      // 获取文件大小
      const contentLength = response.headers.get('Content-Length')
      const fileSize = contentLength ? parseInt(contentLength, 10) : 0

      // 创建 Blob 并下载
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      const sizeMB = (fileSize / (1024 * 1024)).toFixed(2)
      setMessage({
        type: 'success',
        text: `数据库文件下载成功！文件名: ${filename}，大小: ${sizeMB} MB`
      })
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : '下载数据库文件失败'
      })
    } finally {
      setDownloadingDb(false)
    }
  }

  const handleUploadDatabase = async () => {
    if (!selectedFile) {
      setMessage({
        type: 'error',
        text: '请先选择要上传的文件'
      })
      return
    }

    setUploadingDb(true)
    setMessage(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const response = await fetch(`${API_BASE_URL}/api/upload-database`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '上传失败' }))
        throw new Error(errorData.detail || '上传数据库文件失败')
      }

      const result = await response.json()
      setMessage({
        type: 'success',
        text: `数据库文件上传成功！文件名: ${result.filename}，大小: ${result.size_mb} MB，保存路径: ${result.path}`
      })
      setSelectedFile(null)
      // 清空文件选择
      const fileInput = document.getElementById('db-upload-input') as HTMLInputElement
      if (fileInput) {
        fileInput.value = ''
      }
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : '上传数据库文件失败'
      })
    } finally {
      setUploadingDb(false)
    }
  }

  const handleAutoUpdate = async () => {
    setAutoUpdating(true)
    setMessage(null)

    try {
      const payload = {
        interval: selectedInterval,
        auto_split: true,
        request_delay: 0.1,
        batch_size: 30,
        batch_delay: 3.0,
      }

      const response = await fetch(`${API_BASE_URL}/api/auto-update`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        let errorDetail = '自动补全失败'
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
        text: data.message || '自动补全任务已启动',
      })
    } catch (error: any) {
      console.error('自动补全错误:', error)
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
      setAutoUpdating(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">数据库文件管理</h2>
        <p className="text-gray-400">上传和下载数据库文件 (crypto_data.db)</p>
      </div>

      {message && (
        <div
          className={`p-4 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-500/20 text-green-400 border border-green-500/50'
              : 'bg-red-500/20 text-red-400 border border-red-500/50'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* 下载数据库文件 */}
        <div className="p-6 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center mb-4">
            <span className="text-3xl mr-3">📥</span>
            <div>
              <h3 className="text-lg font-semibold">下载数据库文件</h3>
              <p className="text-sm text-gray-400">从服务器下载完整的数据库文件到本地</p>
            </div>
          </div>
          <div className="mt-6">
            <button
              type="button"
              onClick={handleDownloadDatabase}
              disabled={downloadingDb}
              className={`w-full px-6 py-3 rounded-lg font-medium transition-colors ${
                downloadingDb
                  ? 'bg-gray-600 cursor-not-allowed'
                  : 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700'
              }`}
            >
              {downloadingDb ? '下载中...' : '📥 下载数据库文件'}
            </button>
          </div>
          <div className="mt-4 text-xs text-gray-500">
            <p>• 文件将下载到浏览器的默认下载文件夹</p>
            <p>• 文件名格式: crypto_data_YYYYMMDD_HHMMSS.db</p>
          </div>
        </div>

        {/* 上传数据库文件 */}
        <div className="p-6 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center mb-4">
            <span className="text-3xl mr-3">📤</span>
            <div>
              <h3 className="text-lg font-semibold">上传数据库文件</h3>
              <p className="text-sm text-gray-400">上传数据库文件到服务器的 data/tmp 文件夹</p>
            </div>
          </div>
          <div className="mt-6 space-y-4">
            <div>
              <label className="block mb-2">
                <input
                  type="file"
                  accept=".db"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) {
                      if (!file.name.endsWith('.db')) {
                        setMessage({
                          type: 'error',
                          text: '只能上传 .db 文件'
                        })
                        return
                      }
                      setSelectedFile(file)
                      setMessage(null)
                    }
                  }}
                  className="hidden"
                  id="db-upload-input"
                />
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => document.getElementById('db-upload-input')?.click()}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
                  >
                    选择文件
                  </button>
                  {selectedFile && (
                    <div className="flex-1">
                      <p className="text-sm text-gray-300 truncate" title={selectedFile.name}>
                        {selectedFile.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                    </div>
                  )}
                </div>
              </label>
            </div>
            <button
              type="button"
              onClick={handleUploadDatabase}
              disabled={!selectedFile || uploadingDb}
              className={`w-full px-6 py-3 rounded-lg font-medium transition-colors ${
                !selectedFile || uploadingDb
                  ? 'bg-gray-600 cursor-not-allowed'
                  : 'bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700'
              }`}
            >
              {uploadingDb ? '上传中...' : '📤 上传数据库文件'}
            </button>
          </div>
          <div className="mt-4 text-xs text-gray-500">
            <p>• 只支持 .db 格式文件</p>
            <p>• 文件将保存到: data/tmp/</p>
            <p>• 文件名格式: 原文件名_YYYYMMDD_HHMMSS.db</p>
          </div>
        </div>




      </div>


      {/* 使用说明 */}
      <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
        <h4 className="text-sm font-semibold text-blue-400 mb-2">💡 使用说明</h4>
        <ul className="text-xs text-gray-400 space-y-1">
          <li>• <strong>下载</strong>: 从服务器下载当前使用的数据库文件，可用于备份或迁移</li>
          <li>• <strong>上传</strong>: 将数据库文件上传到服务器的临时文件夹，可用于恢复或替换数据库</li>
          <li>• 上传的文件保存在 data/tmp/ 目录，不会自动替换当前使用的数据库</li>
          <li>• 如需替换当前数据库，请手动将上传的文件移动到 data/ 目录并重命名为 crypto_data.db</li>
          <li>• <strong>自动补全</strong>: 自动检测并补全所有交易对的数据，从最后更新日期到当前时间</li>
        </ul>
      </div>
      
      {/* 自动补全功能 */}
      <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
        <div className="bg-gray-800/80 p-6 rounded-lg border border-gray-700">
          <div className="mb-4">
            <h3 className="text-xl font-bold mb-3 text-green-400 flex items-center gap-2">
              <span>🚀</span>
              <span>自动补全数据</span>
            </h3>
            <p className="text-sm text-gray-300 mb-4 leading-relaxed">
              自动检测所有交易对的最后更新日期，并从最后日期补全到当前时间。
              <br />
              对于没有数据的交易对，将从默认开始时间下载。
            </p>
          </div>
          
          {/* 间隔选择器 */}
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2 text-gray-300">
              选择K线间隔
            </label>
            <select
              value={selectedInterval}
              onChange={(e) => setSelectedInterval(e.target.value)}
              disabled={autoUpdating || downloadingDb || uploadingDb}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 text-white"
            >
              {INTERVALS.map((interval) => (
                <option key={interval.value} value={interval.value}>
                  {interval.label}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            onClick={handleAutoUpdate}
            disabled={autoUpdating || downloadingDb || uploadingDb}
            className={`w-full py-4 px-6 rounded-lg font-semibold text-lg transition-all transform ${
              autoUpdating || downloadingDb || uploadingDb
                ? 'bg-gray-600 cursor-not-allowed text-gray-400'
                : 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white shadow-lg hover:shadow-xl hover:scale-[1.02]'
            }`}
            style={{
              minHeight: '50px',
              display: 'block',
              visibility: 'visible',
              opacity: autoUpdating || downloadingDb || uploadingDb ? 0.6 : 1
            }}
          >
            {autoUpdating ? '⏳ 自动补全中...' : '🚀 一键自动补全数据'}
          </button>
          <p className="text-xs text-gray-400 mt-4 text-center">
            将根据选择的K线间隔（<span className="text-green-400 font-semibold">{INTERVALS.find(i => i.value === selectedInterval)?.label || selectedInterval}</span>）自动补全所有交易对的数据
          </p>
        </div>
      </div>
    </div>
  )
}
