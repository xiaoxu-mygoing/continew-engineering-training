<template>
  <a-card title="我的资料" class="general-card">
    <template #extra>
      <a-space wrap>
        <a-button size="small" :disabled="busy" @click="refresh()">刷新</a-button>
        <a-button size="small" status="danger" :disabled="busy || !selectedDocs.length" @click="confirmBatchDelete">
          批量删除<template v-if="selectedDocs.length">（{{ selectedDocs.length }}）</template>
        </a-button>
        <a-button type="primary" size="small" :disabled="busy" @click="uploadPicker?.click()">上传资料</a-button>
      </a-space>
    </template>
    <a-space class="hint" wrap>
      <span>上传资料的建库方式</span>
      <a-radio-group v-model="buildMode" :disabled="busy">
        <a-radio value="rag">RAG</a-radio>
        <a-radio value="graph">GraphRAG</a-radio>
        <a-radio value="both">同时构建</a-radio>
      </a-radio-group>
    </a-space>
    <input ref="uploadPicker" type="file" hidden multiple accept=".txt,.pdf,.docx" @change="onFile($event)" />
    <input ref="replacePicker" type="file" hidden accept=".txt,.pdf,.docx" @change="onFile($event, replacement)" />
    <p class="hint">
      仅自己可见 · 支持多选 PDF、DOCX 或 TXT · 每份最多 5 MB。按选择的方式自动建立索引，替换文件沿用该文件原有方式。
      <a :href="sampleUrl" download="工程实训器材借用指南.txt">下载示例 TXT</a>
    </p>
    <p v-if="progress" class="hint" role="status">正在{{ progress.action }}（{{ progress.done }}/{{ progress.total }}）</p>
    <a-alert v-if="batchIssue" class="hint" type="warning" closable @close="batchIssue = undefined">
      {{ batchIssue.summary }}
      <ul class="batch-failures">
        <li v-for="(failure, index) in batchIssue.failures" :key="index">{{ failure }}</li>
      </ul>
    </a-alert>
    <a-table
      v-model:selected-keys="selectedKeys" class="document-table" size="small"
      :data="documents" row-key="documentId" :loading="busy" :scroll="{ x: 680 }"
      :row-selection="{ type: 'checkbox', showCheckedAll: true, width: 40 }"
      :pagination="{ pageSize: 8, hideOnSinglePage: true }"
    >
      <template #columns>
        <a-table-column title="资料名称" data-index="fileName" :width="140" ellipsis tooltip />
        <a-table-column title="版本" :width="50">
          <template #cell="{ record }">v{{ record.version }}</template>
        </a-table-column>
        <a-table-column title="问答索引" :width="110">
          <template #cell="{ record }">
            <a-space size="mini">
              <a-tooltip :content="record.indexError || statusText[record.indexState as TrainingDocument['indexState']]">
                <a-tag :color="record.indexState === 'failed' ? 'red' : record.indexState === 'ready' ? 'green' : 'blue'">
                  {{ statusText[record.indexState as TrainingDocument['indexState']] }}
                </a-tag>
              </a-tooltip>
              <a-link v-if="record.indexState !== 'pending' && record.indexState !== 'disabled'" :disabled="busy" @click="reindex(record)">
                {{ record.indexState === 'failed' ? '重试' : '重建' }}
              </a-link>
            </a-space>
          </template>
        </a-table-column>
        <a-table-column title="图谱" :width="90">
          <template #cell="{ record }">
            <a-tooltip :content="record.graphError || statusText[record.graphState as TrainingDocument['graphState']]">
              <a-tag :color="record.graphState === 'failed' ? 'red' : record.graphState === 'ready' ? 'green' : 'blue'">
                {{ statusText[record.graphState as TrainingDocument['graphState']] }}
              </a-tag>
            </a-tooltip>
            <a-link v-if="record.graphState === 'failed' || (record.indexState === 'disabled' && record.graphState === 'ready')" :disabled="busy" @click="reindex(record)">
              {{ record.graphState === 'failed' ? '重试' : '重建' }}
            </a-link>
          </template>
        </a-table-column>
        <a-table-column title="更新时间" :width="108">
          <template #cell="{ record }">
            <span class="updated-date">{{ dayjs(record.updatedAt).format('YYYY-MM-DD') }}</span>
            <span class="updated-date">{{ dayjs(record.updatedAt).format('HH:mm') }}</span>
          </template>
        </a-table-column>
        <a-table-column title="操作" :width="142">
          <template #cell="{ record }">
            <div class="document-actions">
              <a-link :disabled="busy" @click="preview(record)">预览</a-link>
              <a-link :disabled="busy || (record.indexState !== 'ready' && record.graphState !== 'ready')" @click="questionDoc = record">问答</a-link>
              <a-link :disabled="busy || record.graphState !== 'ready'" @click="openGraph(record)">图谱</a-link>
              <a-link :disabled="busy" @click="useDownload(() => downloadDocument(record), record.fileName)">下载</a-link>
              <a-link :disabled="busy" @click="chooseReplacement(record)">替换</a-link>
              <a-popconfirm :content="`删除《${record.fileName}》？`" @ok="remove(record)">
                <a-link status="danger" :disabled="busy">删除</a-link>
              </a-popconfirm>
            </div>
          </template>
        </a-table-column>
      </template>
      <template #empty>
        <a-empty :description="loadFailed ? '资料加载失败，请刷新重试' : '还没有资料，点击「上传资料」开始'" />
      </template>
    </a-table>
    <component :is="officePreviewComponent" v-if="officePreviewComponent" ref="officePreview" />
    <DocumentQuestion v-if="questionDoc" :doc="questionDoc" @close="questionDoc = undefined" />
    <a-modal v-model:visible="graphOpen" :title="graphTitle" :width="720" :footer="false" @cancel="closeGraph">
      <GraphCanvas :nodes="graphNodes" :edges="graphEdges" height="380px" @pick="graphPicked = $event" />
      <p v-if="graphPicked" class="hint">点选关系：{{ graphPicked.predicate }} · 依据：{{ graphPicked.evidence }}</p>
      <p v-else class="hint">点击图中的边可以查看支持该关系的原文片段。</p>
    </a-modal>
    <a-modal v-model:visible="showText" :title="textTitle" :footer="false" @close="text = ''">
      <pre class="text-preview">{{ text }}</pre>
    </a-modal>
  </a-card>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { Message, Modal } from '@arco-design/web-vue'
import DocumentQuestion from './DocumentQuestion.vue'
import GraphCanvas from './GraphCanvas.vue'
import type FilePreview from '@/components/FilePreview/index.vue'
import { SessionChangedError, getSessionId } from '@/features/auth-session/access-token'
import { useDownload } from '@/hooks'
import { type BuildMode, type GraphEdge, type GraphNode, type TrainingDocument, deleteDocument, downloadDocument, fetchDocumentGraph, listDocuments, retryIndex, saveDocument } from '@/apis/training/documents'

const emit = defineEmits<{ documents: [rows: TrainingDocument[]] }>()
const documents = ref<TrainingDocument[]>([])
const selectedKeys = ref<(string | number)[]>([])
const selectedDocs = computed(() => {
  const keys = new Set(selectedKeys.value)
  return documents.value.filter((doc) => keys.has(doc.documentId))
})
const buildMode = ref<BuildMode>('both')
const statusText = { disabled: '未启用', ready: '可问答', pending: '建立中', failed: '失败' }
const questionDoc = ref<TrainingDocument>()
const graphOpen = ref(false)
const graphTitle = ref('')
const graphNodes = ref<GraphNode[]>([])
const graphEdges = ref<GraphEdge[]>([])
const graphPicked = ref<GraphEdge>()
const sampleUrl = `${import.meta.env.BASE_URL}training/lab-guide.txt`
const uploadPicker = ref<HTMLInputElement>()
const replacePicker = ref<HTMLInputElement>()
const replacement = ref<TrainingDocument>()
const loading = ref(false)
const working = ref(false)
const busy = computed(() => loading.value || working.value)
const progress = ref<{ action: string, done: number, total: number }>()
const batchIssue = ref<{ summary: string, failures: string[] }>()
const loadFailed = ref(false)
const officePreview = ref<InstanceType<typeof FilePreview>>()
const officePreviewComponent = shallowRef<typeof FilePreview>()
const showText = ref(false)
const textTitle = ref('')
const text = ref('')

let poll: ReturnType<typeof setTimeout> | undefined
let disposed = false
let requestNumber = 0

async function refresh(silent = false) {
  const sequence = ++requestNumber
  clearTimeout(poll)
  if (!silent) loading.value = true
  try {
    const rows = (await listDocuments()).data
    if (disposed || sequence !== requestNumber) return
    documents.value = rows
    const visibleIds = new Set<string | number>(rows.map((doc) => doc.documentId))
    selectedKeys.value = selectedKeys.value.filter((key) => visibleIds.has(key))
    emit('documents', rows)
    if (rows.some((doc) => doc.indexState === 'pending' || doc.graphState === 'pending')) poll = setTimeout(() => refresh(true), 2500)
    loadFailed.value = false
  } catch {
    if (disposed || sequence !== requestNumber) return
    documents.value = []
    emit('documents', [])
    loadFailed.value = true
  } finally {
    if (sequence === requestNumber) loading.value = false
  }
}

async function reindex(doc: TrainingDocument) {
  await retryIndex(doc)
  await refresh()
}

function chooseReplacement(doc: TrainingDocument) {
  if (busy.value) return
  replacement.value = doc
  replacePicker.value?.click()
}

async function runBatch<T>(action: string, items: T[], name: (item: T) => string, perform: (item: T) => Promise<unknown>) {
  if (disposed || busy.value || !items.length) return
  const session = getSessionId()
  const isCurrent = () => !disposed && getSessionId() === session
  const failures: string[] = []
  let succeeded = 0
  working.value = true
  batchIssue.value = undefined
  progress.value = { action, done: 0, total: items.length }
  clearTimeout(poll)
  requestNumber++
  try {
    for (const item of items) {
      if (!isCurrent()) return
      try {
        await perform(item)
        succeeded++
      } catch (error) {
        if (error instanceof SessionChangedError || !isCurrent()) return
        const reason = error instanceof Error ? error.message : '请稍后重试'
        failures.push(`${name(item)}：${reason}`)
      }
      progress.value.done++
    }
    if (!isCurrent()) return
    if (failures.length) {
      batchIssue.value = { summary: `${action}成功 ${succeeded} 项，失败 ${failures.length} 项。`, failures }
    } else {
      Message.success(`已${action} ${succeeded} 份资料`)
    }
  } finally {
    try {
      if (isCurrent()) await refresh()
    } finally {
      progress.value = undefined
      working.value = false
    }
  }
}

function onFile(event: Event, original?: TrainingDocument) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  const mode = buildMode.value
  return runBatch(original ? '更新' : '上传', files, (file) => file.name, async (file) => {
    if (!/\.(pdf|docx|txt)$/i.test(file.name) || !file.size || file.size > 5 * 1024 * 1024) {
      throw new Error('请选择不超过 5 MB 的非空 PDF、DOCX 或 TXT 文件')
    }
    await saveDocument(file, original, original ? undefined : mode)
  })
}

function confirmBatchDelete() {
  const targets = selectedDocs.value
  if (busy.value || !targets.length) return
  const session = getSessionId()
  Modal.warning({
    title: '批量删除资料',
    content: `确定删除已勾选的 ${targets.length} 份资料？对应的问答索引和图谱也会被清理。`,
    okText: '确认删除',
    hideCancel: false,
    maskClosable: false,
    okButtonProps: { status: 'danger' },
    onOk: () => {
      if (getSessionId() === session) return runBatch('删除', targets, (doc) => doc.fileName, deleteDocument)
    },
  })
}

const remove = (doc: TrainingDocument) => runBatch('删除', [doc], (item) => item.fileName, deleteDocument)

async function preview(doc: TrainingDocument) {
  working.value = true
  try {
    const blob: Blob = (await downloadDocument(doc)).data
    const fileType = doc.fileName.split('.').pop()?.toLowerCase()
    if (fileType === 'txt') {
      text.value = await blob.text()
      textTitle.value = doc.fileName
      showText.value = true
    } else {
      officePreviewComponent.value ??= (await import('@/components/FilePreview/index.vue')).default
      await nextTick()
      officePreview.value?.onPreview({ fileInfo: { fileType, fileName: doc.fileName, data: blob } })
    }
  } finally {
    working.value = false
  }
}

async function openGraph(doc: TrainingDocument) {
  graphTitle.value = `《${doc.fileName}》 · v${doc.version} 图谱`
  graphNodes.value = []
  graphEdges.value = []
  graphPicked.value = undefined
  graphOpen.value = true
  try {
    const data = (await fetchDocumentGraph(doc)).data
    graphNodes.value = data.nodes
    graphEdges.value = data.edges
  } catch {
    Message.warning('图谱暂不可用，请稍后重试')
  }
}

function closeGraph() {
  graphOpen.value = false
  graphNodes.value = []
  graphEdges.value = []
  graphPicked.value = undefined
}

onMounted(() => refresh())
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(poll)
})
</script>

<style scoped>
.hint { margin: 0 0 16px; color: var(--color-text-3); }
.batch-failures { max-height: 144px; overflow: auto; margin: 6px 0 0; padding-left: 20px; overflow-wrap: anywhere; }
.document-table :deep(.arco-table-th-title) { white-space: nowrap; }
.document-table :deep(.arco-table-cell) { padding-left: 8px; padding-right: 8px; }
.document-table :deep(.arco-link) { white-space: nowrap; }
.document-actions { display: grid; grid-template-columns: repeat(3, max-content); gap: 2px 4px; }
.updated-date { display: block; white-space: nowrap; }
.text-preview { max-height: 60vh; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
