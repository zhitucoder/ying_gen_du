export function msToClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

const STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  parsing: '解析中',
  downloading: '下载中',
  extracting: '提取音频',
  transcribing: '识别文案',
  segmenting: '切分句子',
  ready: '已完成',
  failed: '处理失败',
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status
}
