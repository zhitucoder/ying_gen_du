<template>
  <view class="page">
    <video
      v-if="videoUrl"
      id="lessonVideo"
      class="video"
      :src="videoUrl"
      :show-center-play-btn="true"
      @timeupdate="onTimeUpdate"
    />

    <view class="toolbar">
      <text class="count">{{ segments.length }} 句</text>
      <text class="hint">点击任意一句开始跟读</text>
    </view>

    <scroll-view scroll-y class="list" :scroll-into-view="scrollInto">
      <view
        v-for="(segment, index) in segments"
        :id="`seg-${index}`"
        :key="segment.id"
        class="sentence"
        :class="{ active: index === activeIndex }"
        @click="openShadow(index)"
      >
        <text class="sentence-index">{{ index + 1 }}</text>
        <view class="sentence-body">
          <text class="sentence-text">{{ segment.text }}</text>
          <text class="sentence-time">{{ msToClock(segment.start_ms) }}</text>
        </view>
      </view>

      <view v-if="segments.length === 0" class="empty">没有识别到文案</view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'

import { api } from '@/api/client'
import type { Segment } from '@/api/types'
import { msToClock } from '@/utils/format'

const projectId = ref(0)
const videoUrl = ref('')
const segments = ref<Segment[]>([])
const activeIndex = ref(-1)
const scrollInto = ref('')

onLoad(async (query) => {
  projectId.value = Number((query as Record<string, string> | undefined)?.id || 0)
  try {
    const [project, transcript] = await Promise.all([
      api.getProject(projectId.value),
      api.getTranscript(projectId.value),
    ])
    videoUrl.value = project.video_url || ''
    segments.value = transcript.segments
  } catch (error) {
    uni.showToast({ title: (error as Error).message, icon: 'none' })
  }
})

function onTimeUpdate(event: { detail?: { currentTime?: number } }) {
  const ms = Math.round((event.detail?.currentTime || 0) * 1000)
  const index = segments.value.findIndex(
    (segment) => ms >= segment.start_ms && ms < segment.end_ms,
  )
  if (index >= 0 && index !== activeIndex.value) {
    activeIndex.value = index
    scrollInto.value = `seg-${index}`
  }
}

function openShadow(index: number) {
  uni.navigateTo({
    url: `/pages/shadow/shadow?id=${projectId.value}&idx=${index}`,
  })
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f6f8;
}

.video {
  width: 100%;
  height: 420rpx;
  background: #000000;
}

.toolbar {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 20rpx 28rpx;
}

.count {
  font-size: 30rpx;
  font-weight: 600;
}

.hint {
  color: #9ca3af;
  font-size: 24rpx;
}

.list {
  flex: 1;
  min-height: 0;
  padding: 0 24rpx;
  box-sizing: border-box;
}

.sentence {
  display: flex;
  align-items: flex-start;
  padding: 24rpx 20rpx;
  margin-bottom: 14rpx;
  background: #ffffff;
  border-radius: 18rpx;
  border: 2rpx solid transparent;
}

.sentence.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.sentence-index {
  width: 48rpx;
  color: #9ca3af;
  font-size: 24rpx;
  line-height: 44rpx;
}

.sentence-body {
  flex: 1;
}

.sentence-text {
  display: block;
  font-size: 30rpx;
  line-height: 1.6;
}

.sentence-time {
  display: block;
  margin-top: 8rpx;
  color: #9ca3af;
  font-size: 22rpx;
}

.empty {
  padding: 80rpx 0;
  text-align: center;
  color: #9ca3af;
  font-size: 26rpx;
}
</style>
