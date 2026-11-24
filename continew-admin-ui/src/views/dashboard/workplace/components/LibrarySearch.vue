<template>
  <a-card title="资料库检索" class="general-card">
    <a-input-search
      v-model="query"
      placeholder="输入设备名、编号或资料名称"
      search-button
      allow-clear
      :max-length="500"
      :loading="loading"
      :disabled="!readyVersions"
      @search="search"
      @clear="reset"
    />
    <p v-if="!readyVersions" class="search-hint">资料的问答索引就绪后即可检索。</p>
    <a-empty v-else-if="searched && !loading && !results.length" description="没有找到相关片段，试试设备名或编号" />
    <ul v-if="results.length" class="search-results" aria-label="检索结果">
      <li v-for="hit in results" :key="`${hit.documentId}-${hit.version}-${hit.chunk}`">
        <div class="search-source">
          <strong>{{ hit.fileName }}</strong>
          <small>v{{ hit.version }} · <template v-if="hit.page">第 {{ hit.page }} 页 · </template>第 {{ hit.chunk }} 段</small>
        </div>
        <p><template v-for="(part, index) in highlighted(hit.text)" :key="index"><mark v-if="part.match">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p>
      </li>
    </ul>
  </a-card>
</template>

<script setup lang="ts">
import { type DocumentSource, type TrainingDocument, searchLibrary } from '@/apis/training/documents'

const props = defineProps<{ documents: TrainingDocument[] }>()
const query = ref('')
const submitted = ref('')
const results = ref<DocumentSource[]>([])
const searched = ref(false)
const loading = ref(false)
const readyVersions = computed(() => props.documents.filter((doc) => doc.indexState === 'ready')
  .map((doc) => `${doc.documentId}:${doc.version}`).sort().join(','))
let sequence = 0

function reset() {
  sequence++
  results.value = []
  searched.value = false
  loading.value = false
}

async function search() {
  const input = query.value.trim()
  if (!input || !readyVersions.value || loading.value) return
  const current = ++sequence
  submitted.value = input
  loading.value = true
  searched.value = false
  results.value = []
  try {
    const response = await searchLibrary(input)
    if (current === sequence) {
      results.value = response.data.results
      searched.value = true
    }
  } catch {
    // 请求拦截器展示错误消息。
  } finally {
    if (current === sequence) loading.value = false
  }
}

function highlighted(text: string) {
  const needle = submitted.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return needle ? text.split(new RegExp(`(${needle})`, 'gi')).map((part, index) => ({ text: part, match: index % 2 === 1 })) : [{ text, match: false }]
}

watch(readyVersions, reset)
onBeforeUnmount(reset)
</script>

<style scoped>
.search-hint, small { color: var(--color-text-3); }
.search-results { list-style: none; padding: 0; margin: 12px 0 0; }
.search-results li { padding: 10px 0; border-bottom: 1px solid var(--color-border-2); }
.search-results li:last-child { border-bottom: 0; padding-bottom: 0; }
.search-source { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 4px 12px; overflow-wrap: anywhere; }
.search-results p { margin: 6px 0 0; color: var(--color-text-2); white-space: pre-wrap; overflow-wrap: anywhere; }
mark { background: rgb(var(--warning-2)); color: var(--color-text-1); border-radius: 2px; }
</style>
