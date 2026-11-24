<template>
  <a-modal v-model:visible="visible" width="min(1000px, calc(100vw - 32px))" title="知识图谱" :footer="false" unmount-on-close>
    <div class="graph-toolbar">
      <span>拖动节点 / 滚轮缩放 / 点击节点查看详情</span>
      <a-button size="small" :loading="loading" @click="loadGraph">
        <template #icon><icon-refresh /></template>
        刷新
      </a-button>
    </div>
    <div class="graph-body">
      <div class="graph-canvas">
        <a-spin v-if="loading" />
        <a-empty v-else-if="!graph.nodes.length" :description="failed ? '图谱加载失败，请刷新重试' : '暂无图谱数据，请先为资料构建图谱'" />
        <VCharts v-else :option="option" autoresize class="chart" @click="onChartClick" />
      </div>
      <aside class="graph-detail" aria-label="实体详情">
        <a-empty v-if="!node" description="点击左侧节点查看实体详情" />
        <template v-else>
          <div class="node-name">
            <strong>{{ node.name }}</strong>
            <a-tag size="small" color="arcoblue">{{ node.kind }}</a-tag>
          </div>
          <section>
            <h4>关联文档</h4>
            <div v-for="name in files" :key="name" class="detail-row">{{ name }}</div>
            <span v-if="!files.length" class="muted">暂无关联文档</span>
          </section>
          <section>
            <h4>关联关系</h4>
            <button v-for="relation in relations" :key="`${relation.documentId}-${relation.id}`" type="button" class="detail-row relation" @click="picked = relation">
              <span class="muted">{{ relation.source === node.id ? '指向' : '来自' }}</span>
              <span :title="neighbor(relation)">{{ neighbor(relation) }}</span>
              <a-tag size="small">{{ relation.predicate }}</a-tag>
            </button>
            <span v-if="!relations.length" class="muted">暂无关联关系</span>
          </section>
          <section v-if="picked?.evidence">
            <h4>关系依据</h4>
            <p class="detail-row">{{ picked.evidence }}</p>
          </section>
        </template>
      </aside>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import VCharts from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { LabelLayout } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import { type DocumentGraph, type GraphEdge, fetchLibraryGraph } from '@/apis/training/documents'

const visible = defineModel<boolean>('visible', { required: true })
const props = defineProps<{ versions: string }>()

use([GraphChart, TooltipComponent, LabelLayout, CanvasRenderer])

const graph = ref<DocumentGraph>({ nodes: [], edges: [] })
const loading = ref(false)
const failed = ref(false)
const selectedId = ref('')
const picked = ref<GraphEdge>()
let request = 0

const nodeById = computed(() => new Map(graph.value.nodes.map((item) => [item.id, item])))
const node = computed(() => nodeById.value.get(selectedId.value))
const relations = computed(() => graph.value.edges.filter((edge) => edge.source === selectedId.value || edge.target === selectedId.value))
const files = computed(() => [...new Set(relations.value.map((edge) => edge.fileName).filter(Boolean))])

function neighbor(edge: GraphEdge) {
  const id = edge.source === selectedId.value ? edge.target : edge.source
  return nodeById.value.get(id)?.name ?? '实体'
}

async function loadGraph() {
  const current = ++request
  graph.value = { nodes: [], edges: [] }
  selectedId.value = ''
  picked.value = undefined
  failed.value = false
  loading.value = true
  try {
    const response = await fetchLibraryGraph()
    if (current === request) graph.value = response.data
  } catch {
    if (current === request) failed.value = true
  } finally {
    if (current === request) loading.value = false
  }
}

watch([visible, () => props.versions], ([open, versions]) => {
  if (open && versions) void loadGraph()
  else request++
})
onBeforeUnmount(() => {
  request++
})

const colors = ['#165DFF', '#00B42A', '#F7BA1E', '#722ED1', '#F53F3F', '#14C9C9', '#FF7D00', '#86909C']
const option = computed<EChartsOption>(() => {
  const kinds = [...new Set(graph.value.nodes.map((item) => item.kind))].sort()
  const density = graph.value.nodes.length
  return {
    tooltip: {
      trigger: 'item',
      renderMode: 'richText',
      confine: true,
      formatter: (params: any) => params.dataType === 'edge' ? params.data.predicate : `${params.data.name}\n类型：${params.data.kind}`,
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      data: graph.value.nodes.map((item) => ({ ...item, symbolSize: density > 70 ? 25 : 32, itemStyle: { color: colors[kinds.indexOf(item.kind) % colors.length] } })),
      edges: graph.value.edges.map((edge) => ({ ...edge, label: { show: density <= 70, formatter: () => edge.predicate, fontSize: 10, color: '#86909C' } })),
      label: { show: true, position: 'right', formatter: '{b}', fontSize: 12, color: 'inherit' },
      labelLayout: { hideOverlap: true },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: 6,
      lineStyle: { color: '#C9CDD4', width: 1.5, curveness: 0.15 },
      force: { repulsion: 260, edgeLength: 140, gravity: 0.1 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 2.5 }, edgeLabel: { show: true } },
    }],
  }
})

function onChartClick(params: { dataType: string, data: { id?: string, source?: string } }) {
  if (params.dataType === 'node' && params.data.id) {
    selectedId.value = params.data.id
    picked.value = undefined
  } else if (params.dataType === 'edge' && params.data.source) {
    selectedId.value = params.data.source
    picked.value = params.data as GraphEdge
  }
}
</script>

<style scoped>
.graph-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; color: var(--color-text-3); font-size: 12px; }
.graph-body { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 16px; }
.graph-canvas, .graph-detail { border: 1px solid var(--color-border-2); border-radius: 6px; background: var(--color-fill-1); }
.graph-canvas { display: grid; place-items: center; min-width: 0; }
.chart { width: 100%; height: 520px; }
.graph-canvas { min-height: 520px; }
.graph-detail { padding: 12px; max-height: 520px; overflow-y: auto; overflow-wrap: anywhere; }
.graph-detail :deep(.arco-empty) { margin-top: 185px; }
.node-name { display: flex; align-items: center; gap: 8px; font-size: 16px; }
h4 { margin: 16px 0 8px; font-size: 13px; font-weight: 500; }
.detail-row { display: block; margin: 0 0 6px; padding: 6px 8px; border: 0; border-radius: 4px; background: var(--color-fill-2); color: var(--color-text-2); font-size: 13px; }
.relation { display: flex; align-items: center; text-align: left; gap: 6px; width: 100%; cursor: pointer; }
.relation span:nth-child(2) { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.relation:hover { background: var(--color-fill-3); }
.muted { color: var(--color-text-3); }
@media (max-width: 760px) {
  .graph-body { grid-template-columns: minmax(0, 1fr); }
  .graph-canvas { min-height: 360px; }
  .chart { height: 360px; }
  .graph-detail { max-height: 230px; }
  .graph-detail :deep(.arco-empty) { margin-top: 0; }
}
</style>
