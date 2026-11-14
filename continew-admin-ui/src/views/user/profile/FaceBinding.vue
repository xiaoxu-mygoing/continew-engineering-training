<template>
  <section class="binding">
    <div>
      <strong>人脸登录</strong>
      <p v-if="status">{{ status.bound ? '已绑定' : '未绑定' }}<span v-if="status.updatedAt"> · {{ dayjs(status.updatedAt).format('YYYY-MM-DD HH:mm') }} 更新</span></p>
      <p v-else>{{ loading ? '正在查询绑定状态' : '暂时无法读取绑定状态' }}</p>
    </div>
    <a-space v-if="status">
      <a-button v-if="status.bound" @click="open(status.identificationEnabled ? 'disable' : 'enable')">
        {{ status.identificationEnabled ? '关闭免输账号登录' : '开启免输账号登录' }}
      </a-button>
      <a-button v-if="status.bound" @click="open('unbind')">解绑</a-button>
      <a-button type="primary" @click="open('bind')">{{ status.bound ? '重新录入' : '绑定人脸' }}</a-button>
    </a-space>
    <a-button v-else :loading="loading" @click="refresh">刷新</a-button>
    <a-modal
      v-model:visible="visible" :title="titles[mode]"
      :ok-loading="busy" :ok-button-props="{ disabled: !canSubmit }" :on-before-ok="submit" @close="reset"
    >
      <a-space direction="vertical" fill>
        <p>{{ descriptions[mode] }}</p>
        <a-input-password v-model="password" autocomplete="current-password" placeholder="请输入当前账号密码" />
        <template v-if="mode === 'bind'">
          <a-checkbox v-model="consent">我同意录入本人的人脸特征</a-checkbox>
          <FaceCamera v-if="visible && consent" ref="camera" guide @ready="ready = $event" />
        </template>
      </a-space>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { Message } from '@arco-design/web-vue'
import FaceCamera from '@/components/FaceCamera/index.vue'
import { type FaceStatus, bindFace, getFaceStatus, setIdentification, unbindFace } from '@/apis/training/face'
import { encryptByRsa } from '@/utils/encrypt'

const status = ref<FaceStatus>()
const loading = ref(false)
const busy = ref(false)
const visible = ref(false)
const consent = ref(false)
const ready = ref(false)
const password = ref('')
const titles = { bind: '录入本人人脸', unbind: '解除人脸绑定', enable: '开启免输账号登录', disable: '关闭免输账号登录' }
const descriptions = {
  bind: '采集画面仅在本机提取特征，用于验证此账号。原图不保存，可随时解绑。',
  unbind: '解绑后，这个账号将停用所有刷脸登录方式。',
  enable: '开启后，系统可在本租户已授权的人脸模板中识别你的账号。下次刷脸无需输入用户名，可随时关闭。',
  disable: '关闭后可继续通过指定账号刷脸登录。',
}
const mode = ref<keyof typeof titles>('bind')
const camera = ref<InstanceType<typeof FaceCamera>>()
const canSubmit = computed(() => !!password.value && (mode.value !== 'bind' || (consent.value && ready.value)))
const expectedVersion = ref(0)

async function refresh() {
  loading.value = true
  try {
    status.value = (await getFaceStatus()).data
  } catch {
    status.value = undefined
  } finally {
    loading.value = false
  }
}
function reset() {
  password.value = ''
  consent.value = false
  ready.value = false
}
function open(action: keyof typeof titles) {
  if (!status.value) return
  reset()
  expectedVersion.value = status.value.templateVersion
  mode.value = action
  visible.value = true
}
async function submit() {
  if (!canSubmit.value || busy.value) return false
  const proof = encryptByRsa(password.value)
  if (!proof) return false
  busy.value = true
  try {
    if (mode.value === 'bind') {
      const image = camera.value?.capture()
      if (!image) return false
      status.value = (await bindFace(proof, expectedVersion.value, image)).data
    } else if (mode.value === 'unbind') {
      status.value = (await unbindFace(proof, expectedVersion.value)).data
    } else {
      status.value = (await setIdentification(mode.value === 'enable', proof, expectedVersion.value)).data
    }
    Message.success('人脸登录设置已更新')
    return true
  } catch {
    await refresh()
    if (status.value?.templateVersion !== expectedVersion.value) visible.value = false
    return false
  } finally {
    busy.value = false
  }
}
onMounted(refresh)
</script>

<style scoped>
.binding { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 14px 0; border-bottom: 1px solid var(--color-border-2); }
.binding p { margin: 4px 0 0; color: var(--color-text-3); }
</style>
