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
    <span role="status">{{ status }}</span>
  </a-space>
</template>

<script setup lang="ts">
import { Message } from '@arco-design/web-vue'
import FaceCamera from '@/components/FaceCamera/index.vue'
import { useTabsStore, useTenantStore, useUserStore } from '@/stores'

const camera = ref<InstanceType<typeof FaceCamera>>()
const username = ref('')
const mode = ref<'identify' | 'verify'>('identify')
const tenant = ref('')
const ready = ref(false)
const status = ref('')
const router = useRouter()
const user = useUserStore()
const tabs = useTabsStore()
const tenantStore = useTenantStore()

watch([ready, mode, username, tenant], ([active, method, account, tenantCode], _, onCleanup) => {
  if (!active) {
    status.value = '开启摄像头后将自动识别。'
    return
  }
  if (method === 'verify' && !account.trim()) {
    status.value = '请输入已绑定的账号，输入后将自动识别。'
    return
  }

  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout>
  let attempts = 0
  onCleanup(() => {
    clearTimeout(timer)
    controller.abort()
  })

  async function recognize() {
    if (controller.signal.aborted) return
    attempts++
    status.value = '正在识别，请正对摄像头…'
    try {
      const image = camera.value?.capture()
      if (!image) throw new Error('摄像头尚未就绪')
      const req = method === 'identify' ? { identify: true, image } : { username: account.trim(), image }
      await user.faceLogin(req, tenantCode.trim(), controller.signal)
    } catch {
      if (controller.signal.aborted) return
      if (attempts < 3) {
        status.value = '本次未通过，请保持单人入镜，稍后会自动再试。'
        timer = setTimeout(recognize, 6000)
      } else {
        status.value = '识别已暂停。请检查账号及人脸设置，再关闭并重新开启摄像头。'
      }
      return
    }
    if (controller.signal.aborted) return
    tabs.reset()
    const target = router.currentRoute.value.query.redirect
    await router.replace(typeof target === 'string' && target.startsWith('/') && !target.startsWith('//') ? target : '/')
    Message.success('人脸验证通过')
  }

  status.value = '请正对摄像头，即将自动识别。'
  timer = setTimeout(recognize, 1000)
}, { immediate: true })
</script>
