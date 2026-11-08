import { API_BASE_URL } from '@/config'

const TOKEN_KEY = 'yg_token'
const USER_KEY = 'yg_user'
const DEVICE_KEY = 'yg_device'

export type SmsScene = 'register' | 'login' | 'reset_password' | 'bind'

export interface AuthUser {
  id: number
  username?: string | null
  nickname?: string | null
  phone?: string | null
  has_password?: boolean
  auth_type: string
  created_at: string
}

export interface SmsSendResult {
  sent: boolean
  retry_after: number
  expires_in: number
}

interface AuthResponse {
  token: string
  user: AuthUser
}

export function getToken(): string {
  return uni.getStorageSync(TOKEN_KEY) || ''
}

export function getUser(): AuthUser | null {
  const raw = uni.getStorageSync(USER_KEY)
  if (!raw) {
    return null
  }
  try {
    return (typeof raw === 'string' ? JSON.parse(raw) : raw) as AuthUser
  } catch {
    return null
  }
}

export function setAuth(token: string, user: AuthUser): void {
  uni.setStorageSync(TOKEN_KEY, token)
  uni.setStorageSync(USER_KEY, JSON.stringify(user))
}

export function clearAuth(): void {
  uni.removeStorageSync(TOKEN_KEY)
  uni.removeStorageSync(USER_KEY)
}

export function isLoggedIn(): boolean {
  return Boolean(getToken())
}

export function getDeviceId(): string {
  let deviceId = uni.getStorageSync(DEVICE_KEY)
  if (!deviceId) {
    deviceId = `dev-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`
    uni.setStorageSync(DEVICE_KEY, deviceId)
  }
  return deviceId
}

function postJson<T>(path: string, data: Record<string, unknown>): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}${path}`,
      method: 'POST',
      data,
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
          return
        }
        const detail = (res.data as { detail?: string } | undefined)?.detail
        reject(new Error(detail || `请求失败 (${res.statusCode})`))
      },
      fail: (err) => reject(new Error(err.errMsg || '网络错误')),
    })
  })
}

function authRequest(path: string, data: Record<string, unknown>): Promise<AuthResponse> {
  return postJson<AuthResponse>(path, data)
}

function authedJson<T>(
  method: 'PATCH' | 'POST',
  path: string,
  data: Record<string, unknown>,
): Promise<T> {
  const token = getToken()
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}${path}`,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
          return
        }
        if (res.statusCode === 401) {
          clearAuth()
        }
        const detail = (res.data as { detail?: string } | undefined)?.detail
        reject(new Error(detail || `请求失败 (${res.statusCode})`))
      },
      fail: (err) => reject(new Error(err.errMsg || '网络错误')),
    })
  })
}

export async function login(account: string, password: string): Promise<AuthUser> {
  const data = await authRequest('/api/auth/login', { username: account, password })
  setAuth(data.token, data.user)
  return data.user
}

export async function register(
  username: string,
  password: string,
  nickname?: string,
): Promise<AuthUser> {
  const data = await authRequest('/api/auth/register', {
    username,
    password,
    nickname: nickname || undefined,
  })
  setAuth(data.token, data.user)
  return data.user
}

export function sendSms(phone: string, scene: SmsScene): Promise<SmsSendResult> {
  return postJson<SmsSendResult>('/api/auth/sms/send', {
    phone,
    scene,
    device_id: getDeviceId(),
  })
}

export async function smsLogin(phone: string, code: string): Promise<AuthUser> {
  const data = await authRequest('/api/auth/sms/login', { phone, code })
  setAuth(data.token, data.user)
  return data.user
}

export async function smsRegister(
  phone: string,
  code: string,
  password: string,
  nickname?: string,
  prefix?: string,
): Promise<AuthUser> {
  const data = await authRequest('/api/auth/sms/register', {
    phone,
    code,
    password,
    nickname: nickname || undefined,
    nickname_prefix: prefix || undefined,
  })
  setAuth(data.token, data.user)
  return data.user
}

export async function updateNickname(nickname: string): Promise<AuthUser> {
  const user = await authedJson<AuthUser>('PATCH', '/api/auth/me', { nickname })
  const token = getToken()
  if (token) {
    setAuth(token, user)
  }
  return user
}

export async function resetPassword(
  phone: string,
  code: string,
  newPassword: string,
): Promise<AuthUser> {
  const data = await authRequest('/api/auth/sms/reset-password', {
    phone,
    code,
    new_password: newPassword,
  })
  setAuth(data.token, data.user)
  return data.user
}
