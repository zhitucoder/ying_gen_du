export interface TaskCreated {
  task_id: number
  status: string
}

export interface TaskStatus {
  task_id: number
  status: string
  progress: number
  error_msg?: string | null
  title?: string | null
  duration_ms?: number | null
}

export interface Segment {
  id: number
  idx: number
  text: string
  start_ms: number
  end_ms: number
  audio_url?: string | null
  video_url?: string | null
}

export interface Project {
  id: number
  title?: string | null
  status: string
  progress: number
  duration_ms?: number | null
  cover_url?: string | null
  source_url?: string | null
  video_url?: string | null
  created_at: string
}

export interface Transcript {
  project_id: number
  title?: string | null
  duration_ms?: number | null
  segments: Segment[]
}

export interface Recording {
  id: number
  segment_id: number
  audio_url?: string | null
  duration_ms?: number | null
  created_at: string
}
