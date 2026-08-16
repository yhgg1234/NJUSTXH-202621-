<template>
  <section class="graph-panel">
    <div class="panel-heading">
      <div>
        <p class="eyebrow">KNOWLEDGE GRAPH</p>
        <h2>岗位能力全景图谱</h2>
        <p class="description">按岗位、技术栈、级别与行业探索技能点之间的关联。</p>
      </div>
      <button class="primary-button" :disabled="loading || optionsLoading" @click="refreshGraph">
        {{ loading ? '加载中…' : '刷新图谱' }}
      </button>
    </div>

    <form class="filters" @submit.prevent="loadGraph">
      <div class="filter-field">
        <span>岗位</span>
        <SearchSelect
          v-model="filters.job_id"
          :options="filterOptions.jobs"
          :disabled="optionsLoading"
          placeholder="全部岗位"
          search-placeholder="搜索岗位名称或 ID"
          empty-label="全部岗位"
          aria-label="岗位"
        />
      </div>
      <label class="filter-field">
        <span>技术栈</span>
        <select v-model="filters.tech_stack" :disabled="optionsLoading">
          <option value="">全部技术栈</option>
          <option v-for="option in filterOptions.tech_stacks" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label class="filter-field">
        <span>岗位级别</span>
        <select v-model="filters.level" :disabled="optionsLoading">
          <option value="">全部级别</option>
          <option v-for="option in levelOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <div class="filter-field">
        <span>行业</span>
        <SearchSelect
          v-model="filters.industry"
          :options="filterOptions.industries"
          :disabled="optionsLoading"
          placeholder="全部行业"
          search-placeholder="搜索行业名称"
          empty-label="全部行业"
          aria-label="行业"
        />
      </div>
      <label class="filter-field">
        <span>数据月份</span>
        <select v-model="filters.period" :disabled="optionsLoading">
          <option value="">最新数据</option>
          <option v-for="option in filterOptions.periods" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <button class="filter-button" type="submit">应用筛选</button>
      <button class="ghost-button" type="button" @click="resetFilters">重置</button>
    </form>
    <p v-if="optionsError" class="filter-error">{{ optionsError }}</p>

    <div class="graph-layout">
      <div class="canvas-wrap">
        <div ref="chartElement" class="graph-canvas" role="img" aria-label="岗位能力关系图"></div>
        <div v-if="error" class="canvas-message error-message">{{ error }}</div>
        <div v-else-if="!loading && graph.nodes.length === 0" class="canvas-message">
          暂无图谱数据，请先导入演示数据或调整筛选条件。
        </div>
        <div class="graph-meta">
          <span>{{ graph.nodes.length }} 个节点</span>
          <span>{{ graph.links.length }} 条关系</span>
          <span v-if="graph.truncated">结果已截断</span>
        </div>
      </div>

      <aside class="detail-card">
        <template v-if="selectedNode">
          <span class="type-chip">{{ typeNames[selectedNode.type] || selectedNode.type }}</span>
          <h3>{{ selectedNode.label }}</h3>
          <p class="node-id">{{ selectedNode.id }}</p>
          <dl>
            <template v-for="(value, key) in visibleProperties" :key="key">
              <dt>{{ key }}</dt>
              <dd>{{ formatValue(value) }}</dd>
            </template>
          </dl>
        </template>
        <div v-else class="detail-placeholder">
          <strong>节点详情</strong>
          <p>点击图中的岗位、技能或行业节点查看属性与溯源信息。</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { GraphChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import kgApi from '../api/kg'
import SearchSelect from './SearchSelect.vue'

echarts.use([GraphChart, LegendComponent, TooltipComponent, CanvasRenderer])

const chartElement = ref(null)
const loading = ref(false)
const optionsLoading = ref(false)
const error = ref('')
const optionsError = ref('')
const selectedNode = ref(null)
const graph = reactive({ nodes: [], links: [], truncated: false })
const filters = reactive({ job_id: '', tech_stack: '', level: '', industry: '', period: '' })
const filterOptions = reactive({ jobs: [], tech_stacks: [], levels: [], industries: [], periods: [] })
let chart
let resizeObserver

const typeNames = {
  Job: '岗位', Skill: '技能', TechStack: '技术栈', Industry: '行业',
  Certificate: '证书', Education: '学历', Project: '项目', Company: '企业', Source: '来源',
}

const typeColors = {
  Job: '#2563eb', Skill: '#10b981', TechStack: '#8b5cf6', Industry: '#f59e0b',
  Certificate: '#ec4899', Education: '#06b6d4', Project: '#f97316', Company: '#64748b', Source: '#94a3b8',
}

const levelNames = {
  intern: '实习', junior: '初级', mid: '中级', senior: '高级', expert: '专家', unknown: '未知',
}
const levelOptions = computed(() => filterOptions.levels.map((option) => ({
  ...option,
  label: `${levelNames[option.value] || option.label}（${option.value}）`,
})))

const visibleProperties = computed(() => {
  if (!selectedNode.value) return {}
  const hidden = new Set(['id', 'name', 'created_at', 'updated_at'])
  return Object.fromEntries(
    Object.entries(selectedNode.value.properties || {}).filter(([key]) => !hidden.has(key)),
  )
})

function formatValue(value) {
  if (Array.isArray(value)) return value.join('、') || '—'
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function buildOption() {
  const types = [...new Set(graph.nodes.map((node) => node.type))]
  const categories = types.map((type) => ({ name: typeNames[type] || type }))
  const typeIndex = Object.fromEntries(types.map((type, index) => [type, index]))
  return {
    color: types.map((type) => typeColors[type] || '#64748b'),
    tooltip: {
      formatter(params) {
        if (params.dataType === 'edge') return `${params.data.source} → ${params.data.target}<br/>${params.data.type}`
        return `<strong>${params.data.name}</strong><br/>${typeNames[params.data.type] || params.data.type}`
      },
    },
    legend: [{ data: categories.map((item) => item.name), bottom: 8, textStyle: { color: '#475569' } }],
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      force: { repulsion: 260, edgeLength: [90, 170], gravity: 0.08 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
      label: { show: true, position: 'right', color: '#1e293b', fontSize: 12 },
      edgeLabel: { show: false },
      lineStyle: { color: 'source', curveness: 0.08, opacity: 0.62 },
      categories,
      data: graph.nodes.map((node) => ({
        ...node, name: node.label, category: typeIndex[node.type],
        symbolSize: node.type === 'Job' ? 48 : node.type === 'Skill' ? 34 : 28,
        itemStyle: { color: typeColors[node.type] || '#64748b' },
      })),
      links: graph.links.map((link) => ({ ...link, value: link.type })),
    }],
  }
}

function renderGraph() {
  if (!chartElement.value) return
  chart ||= echarts.init(chartElement.value)
  chart.clear()
  chart.setOption(buildOption())
  chart.off('click')
  chart.on('click', (params) => {
    if (params.dataType === 'node') selectedNode.value = params.data
  })
}

async function loadGraph() {
  loading.value = true
  error.value = ''
  try {
    const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value))
    const data = await kgApi.getSubgraph({ ...params, limit: 100 })
    Object.assign(graph, data)
    selectedNode.value = null
    await nextTick()
    renderGraph()
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || '无法连接图谱服务，请确认后端与 Neo4j 已启动。'
    Object.assign(graph, { nodes: [], links: [], truncated: false })
    renderGraph()
  } finally {
    loading.value = false
  }
}

async function loadFilterOptions() {
  optionsLoading.value = true
  optionsError.value = ''
  try {
    Object.assign(filterOptions, await kgApi.getFilterOptions())
  } catch {
    optionsError.value = '筛选选项加载失败，请确认后端与 Neo4j 已启动。'
  } finally {
    optionsLoading.value = false
  }
}

async function refreshGraph() {
  await loadFilterOptions()
  await loadGraph()
}

function resetFilters() {
  Object.keys(filters).forEach((key) => { filters[key] = '' })
  loadGraph()
}

onMounted(async () => {
  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(chartElement.value)
  await loadFilterOptions()
  await loadGraph()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
})
</script>

<style scoped>
.graph-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 20px; padding: 28px; box-shadow: 0 18px 50px rgba(15, 23, 42, .08); }
.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.eyebrow { margin: 0 0 5px; color: #2563eb; font-size: 11px; font-weight: 800; letter-spacing: .16em; }
h2 { margin: 0; color: #0f172a; font-size: 26px; }
.description { margin: 8px 0 0; color: #64748b; }
button, input, select { font: inherit; }
button { cursor: pointer; border: 0; border-radius: 9px; font-weight: 650; }
.primary-button { padding: 11px 17px; color: #fff; background: #2563eb; }
.primary-button:disabled { cursor: wait; opacity: .65; }
.filters { display: grid; grid-template-columns: minmax(190px, 1.25fr) repeat(4, minmax(130px, 1fr)) auto auto; gap: 12px; margin: 24px 0 18px; padding: 16px; background: #f8fafc; border-radius: 13px; }
.filter-field { min-width: 0; }
.filter-field > span { display: block; margin-bottom: 6px; color: #475569; font-size: 12px; font-weight: 700; }
select { box-sizing: border-box; width: 100%; height: 40px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0 32px 0 10px; outline: none; color: #0f172a; background: #fff; }
select:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37, 99, 235, .12); }
select:disabled { cursor: wait; color: #94a3b8; background: #f8fafc; }
.filter-error { margin: -10px 16px 16px; color: #b91c1c; font-size: 13px; }
.filter-button, .ghost-button { align-self: end; height: 38px; padding: 0 14px; }
.filter-button { color: #fff; background: #0f172a; }
.ghost-button { color: #334155; background: #e2e8f0; }
.graph-layout { display: grid; grid-template-columns: minmax(0, 1fr) 270px; gap: 18px; }
.canvas-wrap { position: relative; min-height: 570px; overflow: hidden; border: 1px solid #e2e8f0; border-radius: 14px; background: radial-gradient(circle at center, #fff, #f8fafc); }
.graph-canvas { width: 100%; height: 570px; }
.canvas-message { position: absolute; inset: 0; display: grid; place-items: center; padding: 30px; color: #64748b; text-align: center; pointer-events: none; }
.error-message { color: #b91c1c; }
.graph-meta { position: absolute; top: 12px; left: 12px; display: flex; gap: 8px; }
.graph-meta span { padding: 5px 9px; border: 1px solid #e2e8f0; border-radius: 999px; color: #475569; background: rgba(255,255,255,.9); font-size: 11px; }
.detail-card { min-height: 300px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 14px; background: #f8fafc; overflow-wrap: anywhere; }
.detail-card h3 { margin: 12px 0 4px; color: #0f172a; }
.type-chip { display: inline-block; padding: 5px 9px; border-radius: 99px; color: #1d4ed8; background: #dbeafe; font-size: 12px; font-weight: 700; }
.node-id { margin: 0 0 18px; color: #94a3b8; font: 11px ui-monospace, monospace; }
dl { margin: 0; }
dt { margin-top: 13px; color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase; }
dd { margin: 3px 0 0; color: #334155; font-size: 13px; line-height: 1.5; }
.detail-placeholder { color: #64748b; line-height: 1.6; }
.detail-placeholder strong { color: #334155; }
@media (max-width: 1050px) { .filters { grid-template-columns: repeat(2, 1fr); } .graph-layout { grid-template-columns: 1fr; } }
@media (max-width: 620px) { .graph-panel { padding: 18px; } .panel-heading { flex-direction: column; } .filters { grid-template-columns: 1fr; } }
</style>
