import { API_BASE_URL } from '@/config'

import { clearAuth, getToken } from './auth'
import type {
  Project,
  Recording,
  Segment,
  TaskCreated,
  TaskStatus,
  Transcript,
} from './types'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

function detailOf(data: unknown, status: number): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
  }
  return `请求失败 (${status})`
}

function redirectToLogin(): void {
  const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
  const current = pages.length ? pages[pages.length - 1].route || '' : ''
  if (current === 'pages/login/login') {
    return
  }
  uni.reLaunch({ url: '/pages/login/login' })
}

function requireToken(): string {
  const token = getToken()
  if (!token) {
    redirectToLogin()
    throw new ApiError(401, '请先登录')
  }
  return token
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  data?: Record<string, unknown>
}

async function rawRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const token = requireToken()
  return new Promise<T>((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}${path}`,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
          return
        }
        reject(new ApiError(res.statusCode, detailOf(res.data, res.statusCode)))
      },
      fail: (err) => reject(new ApiError(0, err.errMsg || '网络错误')),
    })
  })
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    return await rawRequest<T>(path, options)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      clearAuth()
      redirectToLogin()
    }
    throw error
  }
}

async function upload<T>(
  path: string,
  filePath: string,
  formData: Record<string, string> = {},
): Promise<T> {
  const token = requireToken()
  return new Promise<T>((resolve, reject) => {
    uni.uploadFile({
      url: `${API_BASE_URL}${path}`,
      filePath,
      name: 'file',
      formData,
      header: { Authorization: `Bearer ${token}` },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(res.data) as T)
          } catch {
            reject(new ApiError(res.statusCode, '响应解析失败'))
          }
          return
        }
        if (res.statusCode === 401) {
          clearAuth()
          redirectToLogin()
        }
        let message = `上传失败 (${res.statusCode})`
        try {
          message = detailOf(JSON.parse(res.data), res.statusCode)
        } catch {
          message = res.data || message
        }
        reject(new ApiError(res.statusCode, message))
      },
      fail: (err) => reject(new ApiError(0, err.errMsg || '上传失败')),
    })
  })
}

export async function uploadRecordingBlob(
  segmentId: number,
  blob: Blob,
  durationMs: number,
): Promise<Recording> {
  const token = requireToken()
  const form = new FormData()
  form.append('file', blob, 'recording.webm')
  form.append('duration_ms', String(Math.round(durationMs)))
  const res = await fetch(`${API_BASE_URL}/api/segments/${segmentId}/recordings`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    if (res.status === 401) {
      clearAuth()
      redirectToLogin()
    }
    throw new ApiError(res.status, `上传失败 (${res.status})`)
  }
  return (await res.json()) as Recording
}

export const api = {
  createLinkTask: (url: string) =>
    request<TaskCreated>('/api/tasks', { method: 'POST', data: { url } }),
  uploadTask: (filePath: string, title?: string) =>
    upload<TaskCreated>('/api/tasks/upload', filePath, title ? { title } : {}),
  getTask: (id: number) => request<TaskStatus>(`/api/tasks/${id}`),
  listProjects: () => request<Project[]>('/api/projects'),
  getProject: (id: number) => request<Project>(`/api/projects/${id}`),
  updateProjectTitle: (id: number, title: string) =>
    request<Project>(`/api/projects/${id}`, { method: 'PATCH', data: { title } }),
  deleteProject: (id: number) =>
    request<{ deleted: boolean }>(`/api/projects/${id}`, { method: 'DELETE' }),
  getTranscript: (id: number) => request<Transcript>(`/api/projects/${id}/transcript`),
  getSegments: (id: number) => request<Segment[]>(`/api/projects/${id}/segments`),
  getVideo: (id: number) => request<{ video_url: string }>(`/api/projects/${id}/video`),
  uploadRecording: (segmentId: number, filePath: string, durationMs: number) =>
    upload<Recording>(`/api/segments/${segmentId}/recordings`, filePath, {
      duration_ms: String(Math.round(durationMs)),
    }),
}
