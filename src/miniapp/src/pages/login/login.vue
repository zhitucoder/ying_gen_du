<template>
  <view class="page">
    <view class="brand">
      <text class="title">影跟读</text>
      <text class="subtitle">登录后保存你的跟读历史</text>
    </view>

    <view class="card">
      <view class="tabs">
        <text class="tab" :class="{ active: mode === 'login' }" @click="switchMode('login')">
          登录
        </text>
        <text class="tab" :class="{ active: mode === 'register' }" @click="switchMode('register')">
          注册
        </text>
        <text class="tab" :class="{ active: mode === 'reset' }" @click="switchMode('reset')">
          找回密码
        </text>
      </view>

      <template v-if="mode === 'login'">
        <view class="subtabs">
          <text
            class="subtab"
            :class="{ active: loginMethod === 'password' }"
            @click="switchLoginMethod('password')"
          >
            密码登录
          </text>
          <text
            class="subtab"
            :class="{ active: loginMethod === 'sms' }"
            @click="switchLoginMethod('sms')"
          >
            验证码登录
          </text>
        </view>

        <template v-if="loginMethod === 'password'">
          <input v-model="account" class="input" placeholder="用户名或手机号" :maxlength="32" />
          <input v-model="password" class="input" password placeholder="密码" :maxlength="64" />
          <button class="primary" :disabled="submitting" @click="submitPasswordLogin">
            {{ submitting ? '请稍候...' : '登录' }}
          </button>
          <text class="link" @click="switchMode('reset')">忘记密码？</text>
        </template>

        <template v-else>
          <input v-model="phone" class="input" type="number" placeholder="手机号" :maxlength="11" />
          <view class="code-row">
            <input
              v-model="code"
              class="input code-input"
              type="number"
              placeholder="验证码"
              :maxlength="6"
            />
            <button class="code-btn" :disabled="countdown > 0 || sending" @click="sendCode('login')">
              {{ countdown > 0 ? `${countdown}s` : sending ? '发送中' : '获取验证码' }}
            </button>
          </view>
          <button class="primary" :disabled="submitting" @click="submitSmsLogin">
            {{ submitting ? '请稍候...' : '登录' }}
          </button>
        </template>
      </template>

      <template v-else-if="mode === 'register'">
        <input v-model="phone" class="input" type="number" placeholder="手机号" :maxlength="11" />
        <view class="code-row">
          <input
            v-model="code"
            class="input code-input"
            type="number"
            placeholder="验证码"
            :maxlength="6"
          />
          <button class="code-btn" :disabled="countdown > 0 || sending" @click="sendCode('register')">
            {{ countdown > 0 ? `${countdown}s` : sending ? '发送中' : '获取验证码' }}
          </button>
        </view>
        <input v-model="password" class="input" password placeholder="设置密码（至少 6 位）" :maxlength="64" />
        <input v-model="nickname" class="input" placeholder="昵称（可选，留空自动生成）" :maxlength="64" />
        <view v-if="!nickname.trim()" class="prefix-row">
          <text class="prefix-label">默认昵称</text>
          <text
            v-for="item in prefixOptions"
            :key="item"
            class="prefix-chip"
            :class="{ active: prefix === item }"
            @click="prefix = item"
          >
            {{ item }}
          </text>
        </view>
        <button class="primary" :disabled="submitting" @click="submitRegister">
          {{ submitting ? '请稍候...' : '注册并登录' }}
        </button>
      </template>

      <template v-else>
        <input v-model="phone" class="input" type="number" placeholder="注册手机号" :maxlength="11" />
        <view class="code-row">
          <input
            v-model="code"
            class="input code-input"
            type="number"
            placeholder="验证码"
            :maxlength="6"
          />
          <button class="code-btn" :disabled="countdown > 0 || sending" @click="sendCode('reset_password')">
            {{ countdown > 0 ? `${countdown}s` : sending ? '发送中' : '获取验证码' }}
          </button>
        </view>
        <input v-model="password" class="input" password placeholder="新密码（至少 6 位）" :maxlength="64" />
        <button class="primary" :disabled="submitting" @click="submitReset">
          {{ submitting ? '请稍候...' : '重置密码并登录' }}
        </button>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { ref } from 'vue'

import {
  isLoggedIn,
  login,
  resetPassword,
  sendSms,
  smsLogin,
  smsRegister,
  type SmsScene,
} from '@/api/auth'

type Mode = 'login' | 'register' | 'reset'
type LoginMethod = 'password' | 'sms'

const PHONE_RE = /^1[3-9]\d{9}$/

const mode = ref<Mode>('login')
const loginMethod = ref<LoginMethod>('password')
const account = ref('')
const phone = ref('')
const code = ref('')
const password = ref('')
const nickname = ref('')
const prefix = ref('学神')
const prefixOptions = ['学神', '学霸']
const submitting = ref(false)
const sending = ref(false)
const countdown = ref(0)

let timer: ReturnType<typeof setInterval> | null = null

onLoad(() => {
  if (isLoggedIn()) {
    uni.reLaunch({ url: '/pages/index/index' })
  }
})

onUnload(() => {
  if (timer) {
    clearInterval(timer)
  }
})

function toast(message: string) {
  uni.showToast({ title: message, icon: 'none' })
}

function startCountdown() {
  countdown.value = 60
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0 && timer) {
      clearInterval(timer)
      timer = null
    }
  }, 1000)
}

function switchMode(next: Mode) {
  mode.value = next
  code.value = ''
  password.value = ''
}

function switchLoginMethod(next: LoginMethod) {
  loginMethod.value = next
  code.value = ''
  password.value = ''
}

async function sendCode(scene: SmsScene) {
  if (countdown.value > 0 || sending.value) {
    return
  }
  const value = phone.value.trim()
  if (!PHONE_RE.test(value)) {
    toast('请输入正确的手机号')
    return
  }

  sending.value = true
  try {
    await sendSms(value, scene)
    startCountdown()
    toast('验证码已发送')
  } catch (error) {
    toast((error as Error).message)
  } finally {
    sending.value = false
  }
}

async function run(action: () => Promise<unknown>) {
  submitting.value = true
  try {
    await action()
    uni.reLaunch({ url: '/pages/index/index' })
  } catch (error) {
    toast((error as Error).message)
  } finally {
    submitting.value = false
  }
}

function submitPasswordLogin() {
  const name = account.value.trim()
  if (!name || !password.value) {
    toast('请输入账号和密码')
    return
  }
  run(() => login(name, password.value))
}

function submitSmsLogin() {
  const value = phone.value.trim()
  if (!value || !code.value) {
    toast('请输入手机号和验证码')
    return
  }
  run(() => smsLogin(value, code.value.trim()))
}

function submitRegister() {
  const value = phone.value.trim()
  if (!value || !code.value || !password.value) {
    toast('请填写完整信息')
    return
  }
  if (password.value.length < 6) {
    toast('密码至少 6 位')
    return
  }
  run(() =>
    smsRegister(
      value,
      code.value.trim(),
      password.value,
      nickname.value.trim() || undefined,
      prefix.value,
    ),
  )
}

function submitReset() {
  const value = phone.value.trim()
  if (!value || !code.value || !password.value) {
    toast('请填写完整信息')
    return
  }
  if (password.value.length < 6) {
    toast('密码至少 6 位')
    return
  }
  run(() => resetPassword(value, code.value.trim(), password.value))
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 70rpx 40rpx;
  box-sizing: border-box;
  background: #f5f6f8;
}

.brand {
  padding: 30rpx 8rpx 40rpx;
  text-align: center;
}

.title {
  display: block;
  font-size: 56rpx;
  font-weight: 700;
}

.subtitle {
  display: block;
  margin-top: 12rpx;
  color: #6b7280;
  font-size: 26rpx;
}

.card {
  padding: 32rpx;
  background: #ffffff;
  border-radius: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(15, 23, 42, 0.06);
}

.tabs {
  display: flex;
  gap: 32rpx;
  margin-bottom: 24rpx;
}

.tab {
  padding-bottom: 12rpx;
  color: #9ca3af;
  font-size: 30rpx;
  border-bottom: 4rpx solid transparent;
}

.tab.active {
  color: #2563eb;
  font-weight: 600;
  border-bottom-color: #2563eb;
}

.subtabs {
  display: flex;
  gap: 24rpx;
  margin-bottom: 20rpx;
}

.subtab {
  color: #9ca3af;
  font-size: 26rpx;
}

.subtab.active {
  color: #1f2937;
  font-weight: 600;
}

.input {
  width: 100%;
  height: 88rpx;
  margin-bottom: 20rpx;
  padding: 0 20rpx;
  box-sizing: border-box;
  background: #f3f4f6;
  border-radius: 14rpx;
  font-size: 28rpx;
}

.code-row {
  display: flex;
  gap: 16rpx;
  align-items: flex-start;
}

.code-input {
  flex: 1;
}

.code-btn {
  width: 220rpx;
  height: 88rpx;
  margin: 0;
  padding: 0;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 14rpx;
  font-size: 24rpx;
  line-height: 88rpx;
}

.code-btn[disabled] {
  color: #9ca3af;
  background: #f3f4f6;
}

.prefix-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.prefix-label {
  color: #6b7280;
  font-size: 24rpx;
}

.prefix-chip {
  padding: 8rpx 24rpx;
  border-radius: 999rpx;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 24rpx;
}

.prefix-chip.active {
  background: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}

.primary {
  width: 100%;
  margin-top: 8rpx;
  background: #2563eb;
  color: #ffffff;
  border-radius: 16rpx;
  font-size: 30rpx;
  line-height: 88rpx;
}

.primary[disabled] {
  opacity: 0.6;
}

.link {
  display: block;
  margin-top: 24rpx;
  text-align: center;
  color: #2563eb;
  font-size: 24rpx;
}
</style>
