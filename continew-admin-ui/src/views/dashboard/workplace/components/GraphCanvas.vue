<template>
  <div ref="host" class="graph-canvas" :style="{ height }" />
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import type { GraphEdge, GraphNode } from '@/apis/training/documents'

defineOptions({ name: 'GraphCanvas' })
const props = withDefaults(defineProps<{ nodes: GraphNode[], edges: GraphEdge[], height?: string }>(), {
  height: '320px',
})
const emit = defineEmits<{ pick: [edge: GraphEdge] }>()

const host = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined
let observer: ResizeObserver | undefined

function render() {
  if (!chart) return
  const kinds = [...new Set(props.nodes.map((node) => node.kind))]
  chart.setOption({
    tooltip: {
      renderMode: 'richText',
      formatter: (info: any) => {
        if (info.dataType === 'edge') return `${info.data.predicate}\n${info.data.evidence ?? ''}`
        return `${info.data.kind}：${info.data.name}`
      },
    },
    legend: { data: kinds, bottom: 0 },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      symbolSize: 32,
      label: { show: true, fontSize: 13, position: 'bottom', distance: 8 },
      force: { repulsion: 400, edgeLength: 160 },
      categories: kinds.map((name) => ({ name })),
      edgeSymbol: ['none', 'arrow'],
      edgeLabel: { show: true, fontSize: 10, formatter: (info: any) => info.data.predicate },
      data: props.nodes.map((node) => ({ id: node.id, name: node.name, kind: node.kind, category: kinds.indexOf(node.kind) })),
      links: props.edges.map((edge) => ({
        source: edge.source,
        target: edge.target,
        predicate: edge.predicate,
        evidence: edge.evidence,
        edge,
      })),
    }],
  }, true)
}

onMounted(() => {
  if (!host.value) return
  chart = echarts.init(host.value)
  render()
  chart.on('click', (params: any) => {
    if (params.dataType === 'edge') {
      const hit = params.data.edge as GraphEdge | undefined
      if (hit) emit('pick', hit)
    }
  })
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(host.value)
})

watch(() => [props.nodes, props.edges], render, { deep: true })

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
  chart = undefined
})
</script>

<style scoped>
.graph-canvas { width: 100%; border: 1px solid var(--color-border-2); border-radius: 4px; }
</style>
