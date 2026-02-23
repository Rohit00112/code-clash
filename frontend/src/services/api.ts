import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

const getAccessToken = () => localStorage.getItem('token')
const getRefreshToken = () => localStorage.getItem('refresh_token')

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshing: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  if (refreshing) return refreshing
  refreshing = (async () => {
    const refreshToken = getRefreshToken()
    if (!refreshToken) return null
    try {
      const response = await api.post('/auth/refresh', { refresh_token: refreshToken })
      const newAccess = response.data?.access_token
      const newRefresh = response.data?.refresh_token
      if (newAccess) localStorage.setItem('token', newAccess)
      if (newRefresh) localStorage.setItem('refresh_token', newRefresh)
      return newAccess || null
    } catch {
      return null
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

api.interceptors.response.use(
  (response) => {
    // Unwrap response if it's wrapped in {success, data} structure
    if (response.data && response.data.success !== undefined && response.data.data !== undefined) {
      response.data = response.data.data
    }
    return response
  },
  async (error) => {
    // Only redirect to login on 401 if not already on login page
    if (error.response?.status === 401) {
      const isLoginRequest = error.config?.url?.includes('/auth/login')
      const isRefreshRequest = error.config?.url?.includes('/auth/refresh')
      const cfg: any = error.config || {}
      if (!isLoginRequest && !isRefreshRequest && !cfg._retry) {
        cfg._retry = true
        const nextToken = await refreshAccessToken()
        if (nextToken) {
          cfg.headers = cfg.headers || {}
          cfg.headers.Authorization = `Bearer ${nextToken}`
          return api.request(cfg)
        }
      }
      if (!isLoginRequest) {
        localStorage.removeItem('token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
