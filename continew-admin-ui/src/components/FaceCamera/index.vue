<template>
  <div class="face-camera">
    <video v-show="active" ref="video" autoplay muted playsinline aria-label="摄像头预览" />
    <span v-if="active" aria-live="polite">{{ hint || '仅本人入镜，正对摄像头，保持面部清晰。' }}</span>
    <a-button v-else :disabled="disabled" :loading="opening" @click="start">开启摄像头</a-button>
    <a-button v-if="active" size="mini" @click="stop">关闭摄像头</a-button>
    <span v-if="error" role="alert" class="error">{{ error }}</span>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { checkFaceQuality } from '@/apis/training/face'

const props = defineProps<{ disabled?: boolean, guide?: boolean }>()
const emit = defineEmits<{ (event: 'ready', ready: boolean): void }>()
const video = ref<HTMLVideoElement>()
const active = ref(false)
const opening = ref(false)
const error = ref('')
const hint = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let stream: MediaStream | undefined
let generation = 0

function stop() {
  generation++
  clearTimeout(timer)
  hint.value = ''
  stream?.getTracks().forEach((track) => track.stop())
  stream = undefined
  if (video.value) video.value.srcObject = null
  active.value = false
  opening.value = false
  emit('ready', false)
}

async function start() {
  const current = ++generation
  opening.value = true
  error.value = ''
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('请用 localhost 或 HTTPS 打开系统以使用摄像头')
    const media = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    })
    if (current !== generation || !video.value) {
      media.getTracks().forEach((track) => track.stop())
      return
    }
    stream = media
    video.value.srcObject = media
    await video.value.play()
    if (current !== generation) return
    active.value = true
    emit('ready', true)
    if (props.guide) timer = setTimeout(() => guide(current), 300)
    media.getVideoTracks()[0].onended = () => {
      stop()
      error.value = '摄像头已断开，请重新开启'
    }
  } catch (err) {
    if (current !== generation) return
    stop()
    if (err instanceof DOMException) {
      error.value = err.name === 'NotAllowedError' ? '摄像头权限未开启，请在浏览器地址栏允许使用' : '无法打开摄像头，请检查连接及占用情况'
    } else {
      error.value = err instanceof Error ? err.message : '摄像头不可用'
    }
  } finally {
    if (current === generation) opening.value = false
  }
}

function capture() {
  const el = video.value
  if (!active.value || !el?.videoWidth || !el.videoHeight) return
  const scale = Math.min(1, 640 / Math.max(el.videoWidth, el.videoHeight))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(el.videoWidth * scale)
  canvas.height = Math.round(el.videoHeight * scale)
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.drawImage(el, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
}

async function guide(current: number) {
  if (current !== generation || !active.value) return
  const image = capture()
  if (image) {
    try {
      const { data } = await checkFaceQuality(image)
      if (current === generation) hint.value = data.hint
    } catch {
      // 质量指导不可用时仍可手动采集，由录入接口完成最终校验。
      return
    }
  }
  if (current === generation) timer = setTimeout(() => guide(current), 2200)
}

onBeforeUnmount(stop)
defineExpose({ capture })
</script>

<style scoped>
.face-camera { display: grid; gap: 6px; justify-items: start; color: var(--color-text-2); }
video { display: block; width: 100%; max-height: 180px; background: var(--color-fill-2); border-radius: 6px; object-fit: contain; transform: scaleX(-1); }
.error { color: rgb(var(--danger-6)); }
</style>
