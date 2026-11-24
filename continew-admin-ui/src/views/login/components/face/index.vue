<template>
  <a-space direction="vertical" fill>
    <a-input v-if="tenantStore.needInputTenantCode" v-model="tenant" :disabled="signingIn" placeholder="租户编码（默认租户可留空）" />
    <a-radio-group v-model="mode" :disabled="signingIn" type="button" aria-label="人脸识别方式">
      <a-radio value="identify">免输账号</a-radio>
      <a-radio value="verify">指定账号</a-radio>
    </a-radio-group>
    <a-input v-if="mode === 'verify'" v-model="username" :disabled="signingIn" placeholder="请输入已绑定人脸的账号" :max-length="64" />
    <span v-else>请使用已在「个人中心 → 安全设置」开启免输账号登录的人脸。</span>
    <FaceCamera ref="camera" :disabled="signingIn" @ready="ready = $event" />
    <span role="status" aria-live="polite">{{ status }}</span>
    <a-button v-if="retry && ready" size="small" @click="attempt++">重新验证</a-button>
  </a-space>
</template>

<script setup lang="ts">
import { Message } from '@arco-design/web-vue'
import FaceCamera from '@/components/FaceCamera/index.vue'
import { sendFaceFrame, startFaceSession } from '@/apis/training/face'
import { useTabsStore, useTenantStore, useUserStore } from '@/stores'

const camera = ref<InstanceType<typeof FaceCamera>>()
const username = ref('')
const mode = ref<'identify' | 'verify'>('identify')
const tenant = ref('')
const ready = ref(false)
const status = ref('')
const retry = ref(false)
const signingIn = ref(false)
const attempt = ref(0)
const router = useRouter()
const user = useUserStore()
const tabs = useTabsStore()
const tenantStore = useTenantStore()
let disposed = false
onBeforeUnmount(() => {
  disposed = true
})

watch([ready, mode, username, tenant, attempt], ([active, method, account, tenantCode], _, onCleanup) => {
  if (signingIn.value) return
  retry.value = false
  if (!active) {
    status.value = '开启摄像头后自动开始活体验证，通过后自动登录。'
    return
  }
  if (method === 'verify' && !account.trim()) {
    status.value = '请输入已绑定的账号，输入后将自动开始活体验证。'
    return
  }

  const controller = new AbortController()
  const { signal } = controller
  onCleanup(() => controller.abort())

  function pause(ms: number) {
    signal.throwIfAborted()
    return new Promise<void>((resolve, reject) => {
      let timer: ReturnType<typeof setTimeout>
      const aborted = () => {
        clearTimeout(timer)
        reject(new DOMException('已取消', 'AbortError'))
      }
      timer = setTimeout(() => {
        signal.removeEventListener('abort', aborted)
        resolve()
      }, ms)
      signal.addEventListener('abort', aborted, { once: true })
    })
  }

  async function recognize() {
    let loginStarted = false
    try {
      await pause(700)
      status.value = '正在准备随机动作，请正对摄像头。'
      const context = { clientId: import.meta.env.VITE_CLIENT_ID, identify: method === 'identify', username: method === 'verify' ? account.trim() : undefined }
      const session = (await startFaceSession(context, tenantCode.trim(), signal)).data
      const deadline = Date.now() + 115000
      while (Date.now() < deadline) {
        signal.throwIfAborted()
        const image = camera.value?.capture(640)
        if (!image) throw new Error('摄像头尚未就绪')
        const progress = (await sendFaceFrame(session.sessionId, context, image, tenantCode.trim(), signal)).data
        signal.throwIfAborted()
        if (progress.done) {
          if (!progress.livenessToken) throw new Error(progress.result || '验证未通过')
          loginStarted = true
          signingIn.value = true
          status.value = '人脸与活体验证通过，正在登录…'
          const loginRoute = router.currentRoute.value
          await user.faceLogin({ ...context, image, livenessToken: progress.livenessToken }, tenantCode.trim())
          if (disposed || router.currentRoute.value !== loginRoute) return
          tabs.reset()
          const target = loginRoute.query.redirect
          await router.replace(typeof target === 'string' && target.startsWith('/') && !target.startsWith('//') ? target : '/')
          if (router.currentRoute.value.path === '/login') {
            throw new Error('进入系统失败，请重新验证')
          }
          Message.success('登录成功')
          return
        }
        status.value = progress.action || progress.result || '正在识别…'
        await pause(150)
      }
      throw new Error('验证超时，请重新验证')
    } catch (error) {
      if (!disposed && (loginStarted || !signal.aborted)) {
        retry.value = true
        status.value = error instanceof Error ? error.message : '验证未通过，请重新验证'
      }
    } finally {
      if (loginStarted) signingIn.value = false
    }
  }

  void recognize()
}, { immediate: true })
</script>
