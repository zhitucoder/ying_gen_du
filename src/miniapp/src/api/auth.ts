import { API_BASE_URL } from '@/config'

const TOKEN_KEY = 'yg_token'
const OPENID_KEY = 'yg_openid'

interface LoginResponse {
  token: string
  user_id: number
}

export function getToken(): string {
  return uni.getStorageSync(TOKEN_KEY) || ''
}

export function clearToken(): void {
  uni.removeStorageSync(TOKEN_KEY)
}

function getOpenid(): string {
  let openid = uni.getStorageSync(OPENID_KEY)
  if (!openid) {
    openid = `dev-${Math.random().toString(36).slice(2, 10)}`
    uni.setStorageSync(OPENID_KEY, openid)
  }
  return openid
}

export function ensureLogin(): Promise<string> {
  const existing = getToken()
  if (existing) {
    return Promise.resolve(existing)
  }

  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}/api/auth/login`,
      method: 'POST',
      data: { openid: getOpenid(), nickname: 'dev' },
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          const data = res.data as LoginResponse
          uni.setStorageSync(TOKEN_KEY, data.token)
          resolve(data.token)
        } else {
          reject(new Error(`登录失败 (${res.statusCode})`))
        }
      },
      fail: (err) => reject(new Error(err.errMsg || '网络错误')),
    })
  })
}
