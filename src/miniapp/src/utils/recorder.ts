export interface RecordResult {
  filePath: string
  durationMs: number
  blob?: Blob
}

export interface Recorder {
  start: () => Promise<void>
  stop: () => Promise<RecordResult>
  cancel: () => void
  isRecording: () => boolean
}

const canUseBrowserRecorder =
  typeof navigator !== 'undefined' &&
  !!navigator.mediaDevices &&
  typeof MediaRecorder !== 'undefined'

function createBrowserRecorder(): Recorder {
  let stream: MediaStream | null = null
  let media: MediaRecorder | null = null
  let chunks: BlobPart[] = []
  let startedAt = 0
  let recording = false

  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunks = []
      media = new MediaRecorder(stream)
      media.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data)
        }
      }
      media.start()
      startedAt = Date.now()
      recording = true
    },
    stop() {
      return new Promise<RecordResult>((resolve, reject) => {
        if (!media) {
          reject(new Error('未在录音'))
          return
        }
        media.onstop = () => {
          const blob = new Blob(chunks, { type: media?.mimeType || 'audio/webm' })
          const filePath = URL.createObjectURL(blob)
          stream?.getTracks().forEach((track) => track.stop())
          recording = false
          resolve({ filePath, durationMs: Date.now() - startedAt, blob })
        }
        media.stop()
      })
    },
    cancel() {
      try {
        media?.stop()
      } catch {
        // ignore
      }
      stream?.getTracks().forEach((track) => track.stop())
      recording = false
    },
    isRecording: () => recording,
  }
}

function createUniRecorder(): Recorder {
  const manager = uni.getRecorderManager()
  let recording = false
  let startResolve: (() => void) | null = null
  let startReject: ((error: Error) => void) | null = null
  let stopResolve: ((result: RecordResult) => void) | null = null
  let pendingResult: RecordResult | null = null

  manager.onStart(() => {
    recording = true
    startResolve?.()
    startResolve = null
  })
  manager.onError((error: { errMsg?: string }) => {
    const err = new Error(error?.errMsg || '录音失败')
    startReject?.(err)
    startResolve = null
    startReject = null
    recording = false
  })
  manager.onStop((result: { tempFilePath: string; duration: number }) => {
    recording = false
    const value = {
      filePath: result.tempFilePath,
      durationMs: result.duration || 0,
    }
    if (stopResolve) {
      stopResolve(value)
      stopResolve = null
    } else {
      pendingResult = value
    }
  })

  return {
    start() {
      return new Promise<void>((resolve, reject) => {
        startResolve = resolve
        startReject = reject
        manager.start({
          duration: 60000,
          format: 'mp3',
          sampleRate: 44100,
          numberOfChannels: 1,
        })
      })
    },
    stop() {
      return new Promise<RecordResult>((resolve, reject) => {
        stopResolve = resolve
        if (pendingResult) {
          const value = pendingResult
          pendingResult = null
          resolve(value)
          return
        }
        try {
          manager.stop()
        } catch (error) {
          reject(error as Error)
        }
      })
    },
    cancel() {
      try {
        manager.stop()
      } catch {
        // ignore
      }
      recording = false
    },
    isRecording: () => recording,
  }
}

export function createRecorder(): Recorder {
  return canUseBrowserRecorder ? createBrowserRecorder() : createUniRecorder()
}
