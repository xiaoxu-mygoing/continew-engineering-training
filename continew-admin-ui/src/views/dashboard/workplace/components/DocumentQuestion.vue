<template>
  <a-modal visible title="资料问答" :width="620" :footer="false" @cancel="emit('close')">
    <p v-if="doc" class="scope">《{{ doc.fileName }}》 · v{{ doc.version }} · 仅搜索这份资料</p>
    <p v-else class="scope">搜索我的全部已就绪资料</p>
    <a-textarea v-model="question" placeholder="这份资料里，你想了解什么？" :max-length="500" show-word-limit :auto-size="{ minRows: 2, maxRows: 4 }" />
    <a-button class="send" type="primary" :loading="busy" :disabled="!question.trim()" @click="ask">提问</a-button>
    <p v-if="busy" role="status">正在检索原文并生成回答…</p>
    <a-alert v-else-if="failed" type="error">本次未取得答案，请查看提示后重试。</a-alert>
    <section v-else-if="result" aria-live="polite">
      <strong>回答</strong>
      <p>{{ result.answer }}</p>
      <a-alert v-if="result.workflow && result.workflow.route !== 'answered'" type="info">
        {{ result.workflow.route === 'no_match' ? '没有匹配的段落。可以换用资料里的设备名、编号或关键词再问。' : '找到了相关段落，但无法从中核实答案。请补充写明所问事项的资料。' }}
      </a-alert>
      <blockquote v-for="source in result.sources" :key="`${source.documentId}-${source.chunk}`">
        <small>《{{ source.fileName }}》 · v{{ source.version }} · <template v-if="source.page">第 {{ source.page }} 页 · </template>第 {{ source.chunk }} 段</small>
        <p>{{ source.text }}</p>
      </blockquote>
      <details v-if="result.workflow">
        <summary>查看本次问答流程</summary>
        <ol>
          <li>在当前账号有权查阅的 {{ result.workflow.documents }} 份已就绪资料中检索。</li>
          <li>保留 {{ result.workflow.candidates }} 个相关片段。</li>
          <li v-if="result.workflow.route === 'no_match'">检索结束，跳过答案生成。</li>
          <li v-else>调用本地模型生成答案，核对原文后返回 {{ result.workflow.citations }} 条引用。</li>
        </ol>
      </details>
    </section>
  </a-modal>
</template>

<script setup lang="ts">
import { type DocumentAnswer, type TrainingDocument, askDocument, askLibrary } from '@/apis/training/documents'

defineOptions({ name: 'DocumentQuestion' })
const props = defineProps<{ doc?: TrainingDocument }>()
const emit = defineEmits<{ close: [] }>()
const question = ref('')
const busy = ref(false)
const failed = ref(false)
const result = ref<DocumentAnswer>()

async function ask() {
  if (busy.value || !question.value.trim()) return
  busy.value = true
  failed.value = false
  result.value = undefined
  try {
    const input = question.value.trim()
    const response = props.doc ? await askDocument(props.doc, input) : await askLibrary(input)
    result.value = response.data
  } catch {
    failed.value = true
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.scope, small { color: var(--color-text-3); }
.send { margin: 12px 0; }
details { margin-top: 12px; color: var(--color-text-2); }
summary { cursor: pointer; }
blockquote { margin: 10px 0; padding: 10px 14px; background: var(--color-fill-2); border-left: 3px solid rgb(var(--primary-6)); }
section p { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
