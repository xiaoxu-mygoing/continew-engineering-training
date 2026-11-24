<template>
  <a-card class="general-card" :body-style="{ padding: '12px 16px' }">
    <div class="mode-toolbar">
      <div class="mode-option">
        <span>检索模式</span>
        <a-radio-group v-model="mode" type="button" size="small" :disabled="busy" aria-label="检索模式">
          <a-radio value="rag">RAG</a-radio>
          <a-radio value="graph">GraphRAG</a-radio>
        </a-radio-group>
      </div>
      <div class="graph-stats" aria-label="知识图谱统计">
        <span><strong>{{ stats?.entityCount ?? '–' }}</strong><small>实体</small></span>
        <span><strong>{{ stats?.relationCount ?? '–' }}</strong><small>关系</small></span>
        <span><strong>{{ stats?.documentCount ?? '–' }}</strong><small>图谱文档</small></span>
      </div>
      <a-button size="small" :disabled="!graphVersions" @click="graphOpen = true">
        <template #icon><icon-branch /></template>
        知识图谱
      </a-button>
    </div>
  </a-card>

  <a-card title="AI 智能问答" class="general-card" :body-style="{ padding: 0 }">
    <div class="chat-panel">
      <div ref="chatBody" class="chat-body" role="log" aria-live="polite">
        <div class="chat-row assistant"><div class="chat-bubble">你好！我可以根据「我的资料」回答问题，也可以解答常见问题。</div></div>
        <div v-for="turn in turns" :key="turn.id" class="chat-turn">
          <div class="chat-row user"><div class="chat-bubble">{{ turn.question }}</div></div>
          <div class="chat-row assistant">
            <div class="chat-bubble">
              <small v-if="turn.answer?.workflow?.route === 'general'">通用回答 · 无资料引用</small>
              <small v-else-if="turn.answer?.sources.length">{{ turn.usedFallback ? 'GraphRAG → RAG' : turn.mode === 'graph' ? 'GraphRAG' : 'RAG' }}</small>
              <p v-if="turn.answer">{{ turn.answer.answer }}</p>
              <p v-else>{{ turn.failed ? '未取得回答，请重试。' : '正在生成回答…' }}</p>
              <details v-if="turn.answer?.sources.length">
                <summary>原文依据（{{ turn.answer.sources.length }}）</summary>
                <blockquote v-for="source in turn.answer.sources" :key="`${source.documentId}-${source.version}-${source.chunk}`">
                  <strong>{{ source.fileName }}</strong>
                  <small>v{{ source.version }} · <template v-if="source.page">第 {{ source.page }} 页 · </template>第 {{ source.chunk }} 段</small>
                  <p>{{ source.text }}</p>
                </blockquote>
              </details>
            </div>
          </div>
        </div>
      </div>
      <form class="chat-composer" @submit.prevent="send">
        <a-input
          v-model="question"
          aria-label="问答输入"
          placeholder="请输入问题（Enter 发送）"
          :max-length="500"
          @keydown.enter="onEnter"
        />
        <a-button type="primary" html-type="submit" :loading="busy" :disabled="!question.trim()">
          <template #icon><icon-send /></template>
          发送
        </a-button>
      </form>
    </div>
  </a-card>

  <LibraryGraphDialog v-model:visible="graphOpen" :versions="graphVersions" />
</template>

<script setup lang="ts">
import LibraryGraphDialog from './LibraryGraphDialog.vue'
import { type DocumentAnswer, type GraphAnswer, type GraphStats, type TrainingDocument, askGraph, askLibrary, fetchLibraryGraphStats } from '@/apis/training/documents'

type Mode = 'rag' | 'graph'
interface ChatTurn {
  id: number
  mode: Mode
  question: string
  answer?: DocumentAnswer | GraphAnswer
  usedFallback?: boolean
  failed?: boolean
}

const props = defineProps<{ documents: TrainingDocument[] }>()
const mode = ref<Mode>('rag')
const question = ref('')
const busy = ref(false)
const turns = ref<ChatTurn[]>([])
const chatBody = ref<HTMLDivElement>()
const graphVersions = computed(() => props.documents.filter((doc) => doc.graphState === 'ready')
  .map((doc) => `${doc.documentId}:${doc.version}`).sort().join(','))
const stats = ref<GraphStats>()
const graphOpen = ref(false)
let nextTurn = 0
let statsRequest = 0
let disposed = false

async function scrollToLatest() {
  await nextTick()
  if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
}

async function send() {
  const input = question.value.trim()
  if (!input || busy.value) return
  const retrievalMode = mode.value === 'graph' && graphVersions.value ? 'graph' : 'rag'
  const turn = reactive<ChatTurn>({ id: ++nextTurn, mode: retrievalMode, question: input })
  turns.value.push(turn)
  question.value = ''
  busy.value = true
  await scrollToLatest()
  try {
    if (turn.mode === 'graph') {
      const { data } = await askGraph(input)
      if (disposed) return
      if (data.sources.length) {
        turn.answer = data
        return
      }
      turn.usedFallback = true
    }
    const response = await askLibrary(input)
    if (!disposed) turn.answer = response.data
  } catch {
    if (!disposed) {
      turn.failed = true
      if (!question.value) question.value = input
    }
  } finally {
    busy.value = false
    if (!disposed) await scrollToLatest()
  }
}

function onEnter(event: KeyboardEvent) {
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  void send()
}

watch(graphVersions, async (versions) => {
  const request = ++statsRequest
  if (!versions) {
    graphOpen.value = false
    stats.value = { entityCount: 0, relationCount: 0, documentCount: 0 }
    return
  }
  stats.value = undefined
  try {
    const response = await fetchLibraryGraphStats()
    if (request === statsRequest) stats.value = response.data
  } catch {
    // 统计不可用时保留占位符，问答仍可单独处理。
  }
}, { immediate: true })

onBeforeUnmount(() => {
  disposed = true
  statsRequest++
})
</script>

<style scoped>
.mode-toolbar, .mode-option, .graph-stats { display: flex; align-items: center; gap: 12px; }
.mode-toolbar { justify-content: space-between; flex-wrap: wrap; }
.mode-option { white-space: nowrap; }
.graph-stats { gap: 14px; }
.graph-stats span { display: grid; text-align: center; }
.graph-stats strong { font-size: 17px; line-height: 1.2; }
small { color: var(--color-text-3); }
.chat-panel { display: flex; flex-direction: column; height: clamp(450px, 65vh, 720px); min-height: 0; }
.chat-body { flex: 1; min-height: 0; overflow-y: auto; padding: 20px 16px; }
.chat-row { display: flex; margin-bottom: 14px; }
.chat-row.user { justify-content: flex-end; }
.chat-bubble { max-width: 92%; padding: 10px 14px; border-radius: 10px; background: var(--color-fill-2); white-space: pre-wrap; overflow-wrap: anywhere; }
.user .chat-bubble { background: var(--color-primary-light-1); }
.chat-bubble p { margin: 4px 0 0; }
.chat-bubble details { margin-top: 8px; }
.chat-bubble summary { cursor: pointer; }
.chat-bubble blockquote { margin: 8px 0 0; padding-left: 10px; border-left: 2px solid var(--color-border-3); }
.chat-bubble blockquote small { display: block; }
.chat-composer { display: flex; gap: 10px; padding: 14px 16px; border-top: 1px solid var(--color-border-2); }
.chat-composer :deep(.arco-input-wrapper) { min-width: 0; }
</style>
