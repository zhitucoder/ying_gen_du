<template>
  <view v-if="segment" class="page">
    <video
      v-if="videoUrl"
      id="shadowVideo"
      class="video"
      :src="videoUrl"
      :controls="false"
      :show-center-play-btn="false"
      @timeupdate="onVideoTimeUpdate"
    />

    <view class="sentence-card">
      <text class="progress-text">第 {{ index + 1 }} / {{ segments.length }} 句</text>
      <text class="sentence-text">{{ segment.text }}</text>
      <text class="sentence-time">
        {{ msToClock(segment.start_ms) }} - {{ msToClock(segment.end_ms) }}
      </text>
    </view>

    <view class="actions">
      <button class="primary" @click="playOriginal">▶ 原句</button>
      <button class="record" :class="{ active: recording }" @click="toggleRecord">
        {{ recording ? '■ 停止' : '● 录音' }}
      </button>
    </view>

    <text v-if="uploading" class="uploading">录音上传中…</text>

    <view v-if="recordingUrl" class="recording-card">
      <text class="recording-title">我的录音</text>
      <view class="recording-actions">
        <button class="ghost small" @click="playRecording">▶ 播放</button>
        <button class="ghost small" @click="playCompare">A/B 对比</button>
      </view>
    </view>

    <view class="nav">
      <button class="ghost" :disabled="index === 0" @click="go(-1)">上一句</button>
      <button class="ghost" :disabled="index >= segments.length - 1" @click="go(1)">
        下一句
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'

import { api, uploadRecordingBlob } from '@/api/client'
import type { Segment } from '@/api/types'
import { msToClock } from '@/utils/format'
import { createRecorder, type Recorder } from '@/utils/recorder'

const projectId = ref(0)
const index = ref(0)
const segments = ref<Segment[]>([])
const videoUrl = ref('')
const recordingUrl = ref('')
const recording = ref(false)
const uploading = ref(false)
const playingOriginal = ref(false)
const compareMode = ref(false)

const segment = computed(() => segments.value[index.value])

let recorder: Recorder | null = null
let audio: UniApp.InnerAudioContext | null = null
let stopping: Promise<void> | null = null

function getAudio(): UniApp.InnerAudioContext {
  if (!audio) {
    audio = uni.createInnerAudioContext()
    audio.onEnded(() => {
      if (compareMode.value) {
        compareMode.value = false
        playRecording()
      }
    })
  }
  return audio
}

function videoContext() {
  return uni.createVideoContext('shadowVideo')
}

function seekToSegment() {
  if (videoUrl.value && segment.value) {
    const context = videoContext()
    context.pause()
    context.seek(segment.value.start_ms / 1000)
  }
}

onLoad(async (query) => {
  const params = query as Record<string, string> | undefined
  projectId.value = Number(params?.id || 0)
  index.value = Number(params?.idx || 0)

  try {
    const [project, list] = await Promise.all([
      api.getProject(projectId.value),
      api.getSegments(projectId.value),
    ])
    videoUrl.value = project.video_url || ''
    segments.value = list
    if (index.value >= list.length) {
      index.value = 0
    }
    setTimeout(seekToSegment, 300)
  } catch (error) {
    uni.showToast({ title: (error as Error).message, icon: 'none' })
  }
})

onUnload(() => {
  recorder?.cancel()
  stopPlayback()
  audio?.destroy()
})

function stopPlayback() {
  playingOriginal.value = false
  compareMode.value = false
  if (videoUrl.value) {
    videoContext().pause()
  }
  audio?.stop()
}

async function playOriginalWithCompare(compare: boolean) {
  await finishRecording()
  if (!segment.value) {
    return
  }
  stopPlayback()
  compareMode.value = compare

  if (videoUrl.value) {
    const context = videoContext()
    context.seek(segment.value.start_ms / 1000)
    context.play()
    playingOriginal.value = true
    return
  }

  if (segment.value.audio_url) {
    const player = getAudio()
    player.stop()
    player.src = segment.value.audio_url
    player.play()
    playingOriginal.value = true
  }
}

function playOriginal() {
  void playOriginalWithCompare(false)
}

function onVideoTimeUpdate(event: { detail?: { currentTime?: number } }) {
  if (!playingOriginal.value || !segment.value) {
    return
  }
  const ms = Math.round((event.detail?.currentTime || 0) * 1000)
  if (ms >= segment.value.end_ms) {
    videoContext().pause()
    playingOriginal.value = false
    if (compareMode.value) {
      compareMode.value = false
      playRecording()
    }
  }
}

async function finishRecording(): Promise<void> {
  if (stopping) {
    await stopping
    return
  }
  if (!recording.value) {
    return
  }
  if (!recorder || !segment.value) {
    recording.value = false
    return
  }

  const currentRecorder = recorder
  const currentSegment = segment.value
  stopping = (async () => {
    try {
      const result = await currentRecorder.stop()
      recording.value = false
      uploading.value = true
      const saved = result.blob
        ? await uploadRecordingBlob(
            currentSegment.id,
            result.blob,
            result.durationMs,
          )
        : await api.uploadRecording(
            currentSegment.id,
            result.filePath,
            result.durationMs,
          )
      recordingUrl.value = saved.audio_url || ''
      uni.showToast({ title: '录音已保存', icon: 'success' })
    } catch (error) {
      uni.showToast({ title: (error as Error).message, icon: 'none' })
    } finally {
      recording.value = false
      uploading.value = false
      recorder = null
      stopping = null
    }
  })()
  await stopping
}

async function toggleRecord() {
  if (uploading.value || !segment.value) {
    return
  }

  if (recording.value) {
    await finishRecording()
    return
  }

  stopPlayback()
  recorder = createRecorder()
  try {
    await recorder.start()
    recording.value = true
  } catch (error) {
    recorder = null
    uni.showToast({ title: (error as Error).message, icon: 'none' })
  }
}

async function playRecording() {
  await finishRecording()
  if (!recordingUrl.value) {
    return
  }
  const player = getAudio()
  player.stop()
  player.src = recordingUrl.value
  player.play()
}

async function playCompare() {
  await finishRecording()
  if (!recordingUrl.value) {
    return
  }
  await playOriginalWithCompare(true)
}

async function go(delta: number) {
  await finishRecording()
  const next = index.value + delta
  if (next < 0 || next >= segments.value.length) {
    return
  }
  index.value = next
  stopPlayback()
  recordingUrl.value = ''
  setTimeout(seekToSegment, 200)
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
  background: #f5f6f8;
}

.video {
  width: 100%;
  height: 420rpx;
  background: #000000;
  border-radius: 20rpx;
}

.sentence-card {
  margin-top: 24rpx;
  padding: 32rpx 28rpx;
  background: #ffffff;
  border-radius: 22rpx;
}

.progress-text {
  display: block;
  color: #9ca3af;
  font-size: 24rpx;
}

.sentence-text {
  display: block;
  margin: 18rpx 0 16rpx;
  font-size: 38rpx;
  line-height: 1.6;
  font-weight: 500;
}

.sentence-time {
  color: #9ca3af;
  font-size: 24rpx;
}

.actions {
  display: flex;
  gap: 20rpx;
  margin-top: 24rpx;
}

.actions .primary,
.actions .record {
  flex: 1;
  border-radius: 18rpx;
  font-size: 30rpx;
  line-height: 96rpx;
}

.primary {
  background: #2563eb;
  color: #ffffff;
}

.record {
  background: #ffffff;
  color: #dc2626;
  border: 2rpx solid #fecaca;
}

.record.active {
  background: #fef2f2;
}

.uploading {
  display: block;
  margin-top: 16rpx;
  text-align: center;
  color: #9ca3af;
  font-size: 24rpx;
}

.recording-card {
  margin-top: 24rpx;
  padding: 24rpx 28rpx;
  background: #ffffff;
  border-radius: 20rpx;
}

.recording-title {
  font-size: 28rpx;
  font-weight: 500;
}

.recording-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 16rpx;
}

.ghost {
  background: #ffffff;
  color: #2563eb;
  border: 2rpx solid #bfdbfe;
  border-radius: 16rpx;
  font-size: 28rpx;
  line-height: 80rpx;
}

.small {
  flex: 1;
  line-height: 72rpx;
  font-size: 26rpx;
}

.nav {
  display: flex;
  gap: 20rpx;
  margin-top: 32rpx;
}

.nav .ghost {
  flex: 1;
}

.ghost[disabled] {
  color: #c7d2fe;
  border-color: #e0e7ff;
}
</style>
