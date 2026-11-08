<template>
  <view class="page">
    <view class="panel">
      <text class="title">{{ statusLabel(status) }}</text>
      <view class="bar">
        <view class="bar-inner" :style="{ width: `${progress}%` }" />
      </view>
      <text class="progress">{{ progress }}%</text>
      <text v-if="error" class="error">{{ error }}</text>
      <view v-if="status === 'failed'" class="actions">
        <button class="primary" @click="goHome">返回首页</button>
        <button class="ghost" @click="chooseVideo">上传本地视频</button>
      </view>
      <text v-else class="hint">正在处理，请稍候…</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { ref } from 'vue'

import { api } from '@/api/client'
import { statusLabel } from '@/utils/format'

const projectId = ref(0)
const status = ref('queued')
const progress = ref(0)
const error = ref('')
let timer: ReturnType<typeof setTimeout> | null = null
let stopped = false

async function poll() {
  if (stopped) {
    return
  }
  try {
    const task = await api.getTask(projectId.value)
    status.value = task.status
    progress.value = task.progress
    error.value = task.error_msg || ''

    if (task.status === 'ready') {
      stopped = true
      uni.redirectTo({ url: `/pages/lesson/lesson?id=${projectId.value}` })
      return
    }
    if (task.status === 'failed') {
      stopped = true
      return
    }
  } catch (err) {
    error.value = (err as Error).message
  }
  timer = setTimeout(poll, 1500)
}

onLoad((query) => {
  projectId.value = Number((query as Record<string, string> | undefined)?.id || 0)
  poll()
})

onUnload(() => {
  stopped = true
  if (timer) {
    clearTimeout(timer)
  }
})

function goHome() {
  uni.reLaunch({ url: '/pages/index/index' })
}

function chooseVideo() {
  uni.chooseVideo({
    sourceType: ['album', 'camera'],
    compressed: false,
    success: async (res) => {
      uni.showLoading({ title: '上传中...', mask: true })
      try {
        const task = await api.uploadTask(res.tempFilePath)
        uni.hideLoading()
        uni.redirectTo({ url: `/pages/processing/processing?id=${task.task_id}` })
      } catch (error) {
        uni.hideLoading()
        uni.showToast({ title: (error as Error).message, icon: 'none' })
      }
    },
  })
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40rpx;
  box-sizing: border-box;
}

.panel {
  width: 100%;
  background: #ffffff;
  border-radius: 24rpx;
  padding: 56rpx 40rpx;
  text-align: center;
  box-shadow: 0 8rpx 24rpx rgba(15, 23, 42, 0.06);
}

.title {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
}

.bar {
  height: 16rpx;
  margin: 40rpx 0 20rpx;
  background: #e5e7eb;
  border-radius: 999rpx;
  overflow: hidden;
}

.bar-inner {
  height: 100%;
  background: #2563eb;
  border-radius: 999rpx;
  transition: width 0.3s ease;
}

.progress {
  color: #2563eb;
  font-size: 34rpx;
  font-weight: 600;
}

.error {
  display: block;
  margin-top: 24rpx;
  color: #dc2626;
  font-size: 26rpx;
  word-break: break-all;
}

.hint {
  display: block;
  margin-top: 24rpx;
  color: #9ca3af;
  font-size: 26rpx;
}

.primary {
  width: 100%;
  margin-top: 32rpx;
  background: #2563eb;
  color: #ffffff;
  border-radius: 16rpx;
  font-size: 30rpx;
  line-height: 88rpx;
}

.actions {
  margin-top: 32rpx;
}

.ghost {
  width: 100%;
  margin-top: 16rpx;
  background: #ffffff;
  color: #2563eb;
  border: 2rpx solid #bfdbfe;
  border-radius: 16rpx;
  font-size: 30rpx;
  line-height: 84rpx;
}
</style>
