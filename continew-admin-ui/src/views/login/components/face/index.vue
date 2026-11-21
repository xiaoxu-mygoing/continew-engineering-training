<template>
  <a-space direction="vertical" fill>
    <a-input v-if="tenantStore.needInputTenantCode" v-model="tenant" placeholder="租户编码（默认租户可留空）" />
    <a-radio-group v-model="mode" type="button" aria-label="人脸识别方式">
      <a-radio value="identify">免输账号</a-radio>
      <a-radio value="verify">指定账号</a-radio>
    </a-radio-group>
    <a-input v-if="mode === 'verify'" v-model="username" placeholder="请输入已绑定人脸的账号" :max-length="64" />
    <span v-else>请使用已在「个人中心 → 安全设置」开启免输账号登录的人脸。</span>
    <FaceCamera ref="camera" @ready="ready = $event" />
    <span role="status" aria-live="polite">{{ status }}</span>
    <a-button v-if="retry && ready" size="small" @click="attempt++">重新验证</a-button>
  </a-space>
</template>

<script setup lang="ts">
import { Message } from '@arco-design/web-vue'
import FaceCamera from '@/components/FaceCamera/index.vue'
import { startLiveness, verifyLiveness } from '@/apis/training/face'
import { useTabsStore, useTenantStore, useUserStore } from '@/stores'

const camera = ref<InstanceType<typeof FaceCamera>>()
const username = ref('')
const mode = ref<'identify' | 'verify'>('identify')
const tenant = ref('')
const ready = ref(false)
const status = ref('')
const retry = ref(false)
const attempt = ref(0)
const router = useRouter()
const user = useUserStore()
const tabs = useTabsStore()
const tenantStore = useTenantStore()

watch([ready, mode, username, tenant, attempt], ([active, method, account, tenantCode], _, onCleanup) => {
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
  const batches: string[][] = []
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

  async function capturePhase(frames: string[], count: number) {
    for (let i = 0; i < count; i++) {
      await pause(250)
      const image = camera.value?.capture(320)
      if (!image) throw new Error('摄像头尚未就绪')
      frames.push(image)
    }
  }

  async function recognize() {
    try {
      await pause(700)
      status.value = '正在准备随机动作，请正对摄像头。'
      const context = { clientId: import.meta.env.VITE_CLIENT_ID, identify: method === 'identify', username: method === 'verify' ? account.trim() : undefined }
      const challenge = (await startLiveness(context, tenantCode.trim(), signal)).data
      for (const [index, action] of challenge.actions.entries()) {
        signal.throwIfAborted()
        const frames: string[] = []
        batches.push(frames)
        const label = `活体步骤 ${index + 1}/${challenge.actions.length}`
        status.value = `${label}：先自然睁眼、闭嘴，保持正对摄像头。`
        await capturePhase(frames, 4)
        status.value = `${label}：${action === 'blink' ? '请闭眼保持约1秒，再睁眼' : '请张嘴保持约1秒，再闭嘴'}。`
        await capturePhase(frames, 8)
        status.value = `${label}：恢复自然睁眼、闭嘴，保持不动。`
        await capturePhase(frames, 4)
      }
      status.value = '正在核验活体动作和人脸身份，请稍候…'
      const proof = (await verifyLiveness(challenge.challengeId, context, batches, tenantCode.trim(), signal)).data
      signal.throwIfAborted()
      const last = batches[batches.length - 1]
      const req = { ...context, image: last[last.length - 1], livenessToken: proof.livenessToken }
      await user.faceLogin(req, tenantCode.trim(), signal)
    } catch {
      if (!signal.aborted) {
        retry.value = true
        status.value = '验证未通过。请保持单人入镜、面部清晰，点击重新验证并按提示完成动作。'
      }
      return
    } finally {
      batches.length = 0
    }
    if (signal.aborted) return
    tabs.reset()
    const target = router.currentRoute.value.query.redirect
    await router.replace(typeof target === 'string' && target.startsWith('/') && !target.startsWith('//') ? target : '/')
    Message.success('活体与人脸验证通过')
  }

  void recognize()
}, { immediate: true })
</script>
