<template>
  <view class="page">
    <view class="hero">
      <text class="hero-title">影跟读</text>
      <text class="hero-subtitle">粘贴链接或上传视频，逐句跟读</text>
    </view>

    <view class="card">
      <text class="label">视频链接</text>
      <textarea
        v-model="link"
        class="textarea"
        placeholder="粘贴抖音 / B站 / YouTube 链接或分享文案"
        :maxlength="-1"
        auto-height
      />
      <button class="primary" :disabled="importing" @click="submitLink">
        {{ importing ? '提交中...' : '导入链接' }}
      </button>
      <button class="ghost" @click="chooseVideo">上传本地视频</button>
    </view>

    <view class="section-head">
      <text class="section-title">我的跟读</text>
      <text class="refresh" @click="loadProjects">刷新</text>
    </view>

    <view v-if="loading" class="empty">加载中...</view>
    <view v-else-if="projects.length === 0" class="empty">还没有内容，先导入一个视频吧</view>

    <view v-for="project in projects" :key="project.id" class="project">
      <view class="project-main" @click="openProject(project)">
        <text class="project-title">{{ project.title || `项目 #${project.id}` }}</text>
        <text class="project-meta">
          {{ statusLabel(project.status) }} · {{ msToClock(project.duration_ms || 0) }}
        </text>
      </view>
      <view class="project-side">
        <text class="edit" @click.stop="startEdit(project)">改标题</text>
        <text class="project-badge" :class="project.status" @click="openProject(project)">
          {{ project.status === 'ready' ? '进入' : statusLabel(project.status) }}
        </text>
      </view>
    </view>

    <view v-if="editing" class="modal-mask" @click="cancelEdit">
      <view class="modal" @click.stop>
        <text class="modal-title">修改标题</text>
        <input
          v-model="editTitle"
          class="modal-input"
          :maxlength="80"
          placeholder="输入新标题"
        />
        <view class="modal-actions">
          <button class="ghost" @click="cancelEdit">取消</button>
          <button class="primary" :disabled="saving" @click="saveTitle">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'

import { api } from '@/api/client'
import type { Project } from '@/api/types'
import { msToClock, statusLabel } from '@/utils/format'

const link = ref('')
const importing = ref(false)
const loading = ref(false)
const projects = ref<Project[]>([])
const editing = ref<Project | null>(null)
const editTitle = ref('')
const saving = ref(false)

const URL_RE = /https?:\/\/[^\s，。！？、（）()【】]+/

function extractUrl(text: string): string {
  const matched = text.match(URL_RE)
  return (matched ? matched[0] : text).trim()
}

async function loadProjects() {
  loading.value = true
  try {
    projects.value = await api.listProjects()
  } catch (error) {
    uni.showToast({ title: (error as Error).message, icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function submitLink() {
  const url = extractUrl(link.value)
  if (!url) {
    uni.showToast({ title: '请输入链接', icon: 'none' })
    return
  }
  importing.value = true
  try {
    const task = await api.createLinkTask(url)
    link.value = ''
    uni.navigateTo({ url: `/pages/processing/processing?id=${task.task_id}` })
  } catch (error) {
    uni.showToast({ title: (error as Error).message, icon: 'none' })
  } finally {
    importing.value = false
  }
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
        uni.navigateTo({ url: `/pages/processing/processing?id=${task.task_id}` })
      } catch (error) {
        uni.hideLoading()
        uni.showToast({ title: (error as Error).message, icon: 'none' })
      }
    },
  })
}

function openProject(project: Project) {
  if (project.status === 'ready') {
    uni.navigateTo({ url: `/pages/lesson/lesson?id=${project.id}` })
    return
  }
  if (project.status === 'failed') {
    uni.showToast({ title: '处理失败，请重新导入', icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages/processing/processing?id=${project.id}` })
}

function startEdit(project: Project) {
  editing.value = project
  editTitle.value = project.title || ''
}

function cancelEdit() {
  editing.value = null
  editTitle.value = ''
}

async function saveTitle() {
  if (!editing.value) {
    return
  }
  const title = editTitle.value.trim()
  if (!title) {
    uni.showToast({ title: '标题不能为空', icon: 'none' })
    return
  }

  saving.value = true
  try {
    const updated = await api.updateProjectTitle(editing.value.id, title)
    const index = projects.value.findIndex((item) => item.id === updated.id)
    if (index >= 0) {
      projects.value[index] = updated
    }
    cancelEdit()
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (error) {
    uni.showToast({ title: (error as Error).message, icon: 'none' })
  } finally {
    saving.value = false
  }
}

onShow(() => {
  loadProjects()
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24rpx 24rpx 60rpx;
  box-sizing: border-box;
}

.hero {
  padding: 24rpx 8rpx 32rpx;
}

.hero-title {
  display: block;
  font-size: 52rpx;
  font-weight: 700;
}

.hero-subtitle {
  display: block;
  margin-top: 8rpx;
  color: #6b7280;
  font-size: 26rpx;
}

.card {
  background: #ffffff;
  border-radius: 24rpx;
  padding: 28rpx;
  box-shadow: 0 8rpx 24rpx rgba(15, 23, 42, 0.06);
}

.label {
  font-size: 26rpx;
  color: #6b7280;
}

.textarea {
  width: 100%;
  min-height: 140rpx;
  margin: 16rpx 0 24rpx;
  padding: 20rpx;
  box-sizing: border-box;
  background: #f3f4f6;
  border-radius: 16rpx;
  font-size: 28rpx;
}

.primary {
  width: 100%;
  background: #2563eb;
  color: #ffffff;
  border-radius: 16rpx;
  font-size: 30rpx;
  line-height: 88rpx;
}

.primary[disabled] {
  opacity: 0.6;
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

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 40rpx 8rpx 16rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: 600;
}

.refresh {
  color: #2563eb;
  font-size: 26rpx;
}

.empty {
  padding: 80rpx 0;
  text-align: center;
  color: #9ca3af;
  font-size: 26rpx;
}

.project {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 26rpx 28rpx;
  margin-bottom: 16rpx;
  background: #ffffff;
  border-radius: 20rpx;
}

.project-main {
  flex: 1;
  min-width: 0;
}

.project-title {
  display: block;
  font-size: 30rpx;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-meta {
  display: block;
  margin-top: 8rpx;
  color: #6b7280;
  font-size: 24rpx;
}

.project-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  margin-left: 16rpx;
}

.edit {
  color: #2563eb;
  font-size: 24rpx;
}

.project-badge {
  margin-top: 10rpx;
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
  background: #eff6ff;
  color: #2563eb;
  font-size: 24rpx;
}

.project-badge.failed {
  background: #fef2f2;
  color: #dc2626;
}

.project-badge.ready {
  background: #ecfdf5;
  color: #059669;
}

.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40rpx;
  background: rgba(15, 23, 42, 0.45);
}

.modal {
  width: 100%;
  padding: 32rpx;
  background: #ffffff;
  border-radius: 24rpx;
}

.modal-title {
  display: block;
  margin-bottom: 20rpx;
  font-size: 32rpx;
  font-weight: 600;
}

.modal-input {
  width: 100%;
  height: 88rpx;
  padding: 0 20rpx;
  box-sizing: border-box;
  background: #f3f4f6;
  border-radius: 14rpx;
  font-size: 28rpx;
}

.modal-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 28rpx;
}

.modal-actions .primary,
.modal-actions .ghost {
  flex: 1;
  margin-top: 0;
  line-height: 84rpx;
}
</style>
