<template>
  <div class="page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">JOB EVOLUTION</p>
        <h2>岗位能力动态演化</h2>
        <p>按月度或季度观察岗位技能需求、相邻期变化与趋势证据。</p>
      </div>
    </div>

    <form class="filters" @submit.prevent="loadEvolution">
      <label>
        <span>岗位 ID</span>
        <input v-model.trim="filters.job_id" placeholder="job:backend-engineer" required />
      </label>
      <label>
        <span>粒度</span>
        <select v-model="filters.granularity">
          <option value="quarterly">季度</option>
          <option value="monthly">月度</option>
        </select>
      </label>
      <label>
        <span>开始日期</span>
        <input v-model="filters.start" type="date" />
      </label>
      <label>
        <span>结束日期</span>
        <input v-model="filters.end" type="date" />
      </label>
      <label>
        <span>跨期展示技能数</span>
        <input v-model.number="filters.top_n" type="number" min="1" max="30" />
      </label>
      <label>
        <span>变化阈值（%）</span>
        <input v-model.number="filters.change_threshold_percent" type="number" min="0" max="100" step="1" />
      </label>
      <label>
        <span>预测月数</span>
        <input v-model.number="filters.prediction_horizon_months" type="number" min="1" max="12" />
      </label>
      <button class="primary-button" :disabled="loading" type="submit">
        {{ loading ? '分析中…' : '运行分析' }}
      </button>
    </form>

    <p class="hint">时间范围按资料真实发布时间归期；统计采用去重 JD 占比，而非关键词原始出现次数。</p>

    <div v-if="error" class="message error-message">{{ error }}</div>
    <div v-else-if="!result && !loading" class="message">填写岗位 ID 与时间范围后运行分析。</div>

    <template v-if="result">
      <section class="summary-grid">
        <article class="summary-card">
          <span>分析岗位</span>
          <strong>{{ result.job_title }}</strong>
          <small>{{ result.job_id }}</small>
        </article>
        <article class="summary-card">
          <span>时间周期</span>
          <strong>{{ result.data_quality.period_count }}</strong>
          <small>至少 4 期可形成完整演化结论</small>
        </article>
        <article class="summary-card">
          <span>累计有效 JD</span>
          <strong>{{ result.data_quality.total_jd_count }}</strong>
          <small>各期样本量之和</small>
        </article>
        <article class="summary-card">
          <span>趋势外推</span>
          <strong>{{ result.prediction.available ? '可用' : '暂不可用' }}</strong>
          <small>{{ result.prediction.model || result.prediction.reason }}</small>
        </article>
      </section>

      <section v-if="result.data_quality.warnings.length" class="quality-panel">
        <strong>数据质量提示</strong>
        <ul>
          <li v-for="warning in result.data_quality.warnings" :key="warning">{{ warning }}</li>
        </ul>
      </section>

      <section class="chart-grid">
        <article class="panel chart-panel">
          <div class="panel-title">
            <div>
              <h3>技能需求占比趋势</h3>
              <p>展示各期 Top 技能在该岗位有效 JD 中的覆盖率。</p>
            </div>
          </div>
          <div ref="trendElement" class="chart" role="img" aria-label="岗位技能需求趋势折线图"></div>
        </article>
        <article class="panel chart-panel">
          <div class="panel-title">
            <div>
              <h3>技能 × 时间热力图</h3>
              <p>颜色越深，表示该技能在当期岗位 JD 中的需求占比越高。</p>
            </div>
          </div>
          <div ref="heatmapElement" class="chart" role="img" aria-label="岗位技能时间热力图"></div>
        </article>
      </section>

      <section class="panel changes-panel">
        <div class="panel-title changes-heading">
          <div>
            <h3>相邻期能力变化</h3>
            <p>新增、移除和显著增强/减弱的技能均保留证据来源。</p>
          </div>
          <select v-model="selectedPeriod">
            <option v-for="point in result.timeline" :key="point.period" :value="point.period">
              {{ point.period }}
            </option>
          </select>
        </div>
        <div v-if="selectedPoint?.changes_from_previous?.length" class="change-list">
          <article v-for="change in selectedPoint.changes_from_previous" :key="`${selectedPoint.period}-${change.skill_id}`" class="change-item">
            <span class="change-badge" :class="change.change_type">{{ changeLabel(change.change_type) }}</span>
            <div>
              <strong>{{ change.skill_name }}</strong>
              <p>{{ formatRatio(change.previous_demand_ratio) }} → {{ formatRatio(change.current_demand_ratio) }}（{{ formatDelta(change.delta) }}）</p>
              <small v-if="change.evidence_ids.length">证据：{{ change.evidence_ids.join('、') }}</small>
              <small v-else>暂无可用证据</small>
            </div>
          </article>
        </div>
        <div v-else-if="selectedPointIndex === 0" class="empty-state">首个周期作为基准快照，不计算相邻期变化。</div>
        <div v-else class="empty-state">该周期没有超过当前阈值的技能变化。</div>
      </section>

      <section class="trend-grid">
        <article class="panel trend-panel">
          <h3>热门技能</h3>
          <ol v-if="result.hot_trends.length">
            <li v-for="trend in result.hot_trends" :key="trend.skill_id">
              <span>{{ trend.skill_name }}</span>
              <strong>{{ formatDelta(trend.delta) }}</strong>
            </li>
          </ol>
          <p v-else class="empty-state">当前没有显著上升技能。</p>
        </article>
        <article class="panel trend-panel">
          <h3>衰退技能</h3>
          <ol v-if="result.cold_trends.length">
            <li v-for="trend in result.cold_trends" :key="trend.skill_id">
              <span>{{ trend.skill_name }}</span>
              <strong>{{ formatDelta(trend.delta) }}</strong>
            </li>
          </ol>
          <p v-else class="empty-state">当前没有显著下降技能。</p>
        </article>
        <article class="panel trend-panel prediction-panel">
          <h3>未来 {{ result.prediction.horizon_months }} 个月趋势</h3>
          <p>{{ result.prediction.reason }}</p>
          <div v-if="result.prediction.available && result.prediction.rising_skills.length" class="skill-tags">
            <span v-for="skill in result.prediction.rising_skills" :key="skill">{{ skill }}</span>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { HeatmapChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import jobsApi from '../api/jobs'

echarts.use([LineChart, HeatmapChart, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent, CanvasRenderer])

const loading = ref(false)
const error = ref('')
const result = ref(null)
const selectedPeriod = ref('')
const trendElement = ref(null)
const heatmapElement = ref(null)
const filters = reactive({
  job_id: 'job:backend-engineer',
  granularity: 'quarterly',
  start: '2024-01-01',
  end: '2025-12-31',
  top_n: 10,
  change_threshold_percent: 5,
  prediction_horizon_months: 6,
})

let trendChart
let heatmapChart
let resizeObserver

const selectedPoint = computed(() => result.value?.timeline.find((point) => point.period === selectedPeriod.value))
const selectedPointIndex = computed(() => result.value?.timeline.findIndex((point) => point.period === selectedPeriod.value) ?? -1)
const periods = computed(() => result.value?.timeline.map((point) => point.period) || [])
const topSkills = computed(() => {
  const scores = new Map()
  result.value?.timeline.forEach((point) => {
    point.skill_set.forEach((skill) => {
      const current = scores.get(skill.skill_id)
      scores.set(skill.skill_id, {
        id: skill.skill_id,
        name: skill.skill_name,
        score: Math.max(current?.score || 0, skill.demand_ratio),
      })
    })
  })
  return [...scores.values()].sort((a, b) => b.score - a.score || a.name.localeCompare(b.name)).slice(0, filters.top_n)
})

function formatRatio(value) {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function formatDelta(value) {
  if (value === null || value === undefined) return '—'
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

function changeLabel(type) {
  return ({ added: '新增', removed: '移除', increased: '增强', decreased: '减弱' })[type] || type
}

function seriesForSkill(skillId) {
  return result.value.timeline.map((point) => {
    const skill = point.skill_set.find((item) => item.skill_id === skillId)
    return skill ? Number((skill.demand_ratio * 100).toFixed(2)) : 0
  })
}

function renderCharts() {
  if (!result.value || !trendElement.value || !heatmapElement.value) return
  trendChart ||= echarts.init(trendElement.value)
  heatmapChart ||= echarts.init(heatmapElement.value)
  resizeObserver?.observe(trendElement.value)
  resizeObserver?.observe(heatmapElement.value)

  trendChart.setOption({
    tooltip: { trigger: 'axis', valueFormatter: (value) => `${value}%` },
    legend: { type: 'scroll', bottom: 0 },
    grid: { left: 45, right: 20, top: 25, bottom: 58 },
    xAxis: { type: 'category', data: periods.value },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    series: topSkills.value.map((skill) => ({
      name: skill.name,
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: seriesForSkill(skill.id),
    })),
  }, true)

  const heatmapData = []
  topSkills.value.forEach((selectedSkill, skillIndex) => {
    periods.value.forEach((period, periodIndex) => {
      const point = result.value.timeline[periodIndex]
      const skill = point.skill_set.find((item) => item.skill_id === selectedSkill.id)
      heatmapData.push([periodIndex, skillIndex, skill ? Number((skill.demand_ratio * 100).toFixed(2)) : 0])
    })
  })
  heatmapChart.setOption({
    tooltip: { position: 'top', formatter: (item) => `${topSkills.value[item.value[1]].name}<br/>${periods.value[item.value[0]]}: ${item.value[2]}%` },
    grid: { left: 100, right: 35, top: 20, bottom: 44 },
    xAxis: { type: 'category', data: periods.value, splitArea: { show: true } },
    yAxis: { type: 'category', data: topSkills.value.map((skill) => skill.name), splitArea: { show: true } },
    visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#eff6ff', '#60a5fa', '#1d4ed8'] } },
    series: [{ type: 'heatmap', data: heatmapData, label: { show: true, formatter: (item) => item.value[2] ? `${item.value[2]}%` : '' } }],
  }, true)
}

async function loadEvolution() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await jobsApi.analyzeEvolution({
      job_id: filters.job_id,
      granularity: filters.granularity,
      time_range: filters.start && filters.end ? [filters.start, filters.end] : null,
      top_n: filters.top_n,
      change_threshold: filters.change_threshold_percent / 100,
      prediction_horizon_months: filters.prediction_horizon_months,
    })
    result.value = data
    selectedPeriod.value = data.timeline.at(-1)?.period || ''
    await nextTick()
    renderCharts()
  } catch (requestError) {
    result.value = null
    error.value = requestError.response?.data?.detail || '无法完成演化分析，请确认后端服务、岗位 ID 与历史周期数据。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    trendChart?.resize()
    heatmapChart?.resize()
  })
  if (trendElement.value) resizeObserver.observe(trendElement.value)
  if (heatmapElement.value) resizeObserver.observe(heatmapElement.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  trendChart?.dispose()
  heatmapChart?.dispose()
})
</script>

<style scoped>
.page { animation: fadeIn .3s ease; }
.page-heading { margin-bottom: 20px; }
.eyebrow { margin: 0 0 5px; color: #2563eb; font-size: 11px; font-weight: 800; letter-spacing: .16em; }
h2, h3, p { margin-top: 0; }
h2 { margin-bottom: 8px; color: #0f172a; font-size: 26px; }
.page-heading p:last-child { margin-bottom: 0; color: #64748b; }
.filters { display: grid; grid-template-columns: minmax(180px, 1.6fr) repeat(6, minmax(105px, 1fr)) auto; gap: 12px; align-items: end; padding: 18px; border: 1px solid #dbeafe; border-radius: 16px; background: #f8fbff; }
label span { display: block; margin-bottom: 6px; color: #475569; font-size: 12px; font-weight: 700; }
input, select { box-sizing: border-box; width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; padding: 9px 10px; color: #0f172a; background: #fff; font: inherit; }
input:focus, select:focus { border-color: #2563eb; outline: none; box-shadow: 0 0 0 3px rgba(37, 99, 235, .12); }
.primary-button { height: 39px; padding: 0 16px; border: 0; border-radius: 9px; color: #fff; background: #2563eb; font: inherit; font-weight: 700; cursor: pointer; }
.primary-button:disabled { cursor: wait; opacity: .65; }
.hint { margin: 10px 2px 18px; color: #64748b; font-size: 12px; }
.message, .quality-panel { margin: 18px 0; padding: 14px 16px; border-radius: 12px; color: #475569; background: #f8fafc; }
.error-message { color: #b91c1c; background: #fef2f2; }
.summary-grid, .chart-grid, .trend-grid { display: grid; gap: 16px; margin-bottom: 16px; }
.summary-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.summary-card, .panel { border: 1px solid #e2e8f0; border-radius: 16px; background: #fff; box-shadow: 0 4px 18px rgba(15, 23, 42, .04); }
.summary-card { display: flex; min-height: 100px; flex-direction: column; padding: 17px; }
.summary-card span, .summary-card small { color: #64748b; font-size: 12px; }
.summary-card strong { margin: 8px 0 5px; overflow-wrap: anywhere; color: #0f172a; font-size: 18px; }
.quality-panel { border: 1px solid #fde68a; color: #92400e; background: #fffbeb; }
.quality-panel strong { display: block; margin-bottom: 6px; }
.quality-panel ul { margin: 0; padding-left: 18px; }
.chart-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.panel { padding: 20px; }
.panel-title { display: flex; justify-content: space-between; gap: 16px; }
.panel-title h3, .trend-panel h3 { margin-bottom: 5px; color: #0f172a; font-size: 16px; }
.panel-title p, .prediction-panel p { margin-bottom: 0; color: #64748b; font-size: 12px; line-height: 1.55; }
.chart { height: 330px; margin-top: 12px; }
.changes-heading { align-items: center; }
.changes-heading select { width: 130px; }
.change-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 16px; }
.change-item { display: flex; gap: 11px; padding: 13px; border-radius: 12px; background: #f8fafc; }
.change-item strong { color: #0f172a; }
.change-item p, .change-item small { display: block; margin: 5px 0 0; color: #64748b; font-size: 12px; }
.change-badge { flex: 0 0 auto; height: fit-content; padding: 4px 7px; border-radius: 999px; font-size: 11px; font-weight: 800; }
.added, .increased { color: #047857; background: #d1fae5; }
.removed, .decreased { color: #b91c1c; background: #fee2e2; }
.trend-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.trend-panel ol { margin: 14px 0 0; padding: 0; list-style: none; }
.trend-panel li { display: flex; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid #f1f5f9; color: #334155; }
.trend-panel li strong { color: #2563eb; }
.prediction-panel { background: linear-gradient(145deg, #eff6ff, #fff); }
.skill-tags { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 14px; }
.skill-tags span { padding: 5px 8px; border-radius: 999px; color: #1d4ed8; background: #dbeafe; font-size: 12px; font-weight: 700; }
.empty-state { margin: 16px 0 0; color: #94a3b8; font-size: 13px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 1150px) { .filters { grid-template-columns: repeat(3, minmax(0, 1fr)); } .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 820px) { .chart-grid, .trend-grid { grid-template-columns: 1fr; } }
@media (max-width: 620px) { .filters, .summary-grid { grid-template-columns: 1fr; } .panel { padding: 16px; } .chart { height: 280px; } .changes-heading { align-items: stretch; flex-direction: column; } .changes-heading select { width: 100%; } }
</style>
