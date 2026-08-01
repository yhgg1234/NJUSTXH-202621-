<template>
  <div class="page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">NEW JOB DISCOVERY · 子任务 2.4</p>
        <h2>新岗位发现</h2>
        <p>基于图谱技能组合聚类与 JD 趋势分析，自动识别新兴岗位候选，支持人工审核采纳。</p>
      </div>
    </div>

    <!-- 触发发现 -->
    <form class="filters" @submit.prevent="runDiscovery">
      <label>
        <span>最低置信度</span>
        <input v-model.number="filters.min_confidence" type="number" min="0" max="1" step="0.05" />
      </label>
      <label>
        <span>最大候选数</span>
        <input v-model.number="filters.max_candidates" type="number" min="1" max="100" />
      </label>
      <button class="primary-button" :disabled="loading" type="submit">
        {{ loading ? '分析中…' : '执行新岗位发现' }}
      </button>
    </form>

    <div v-if="error" class="message error-message">{{ error }}</div>
    <div v-else-if="!candidates.length && !loading" class="message">点击上方按钮执行新岗位发现分析。</div>

    <template v-if="candidates.length">
      <!-- 统计概览 -->
      <section class="summary-grid">
        <article class="summary-card">
          <span>候选新岗位</span>
          <strong>{{ stats.total_candidates || candidates.length }}</strong>
          <small>待审核</small>
        </article>
        <article class="summary-card">
          <span>已采纳</span>
          <strong class="text-green">{{ stats.adopted_count || 0 }}</strong>
          <small>已写入图谱</small>
        </article>
        <article class="summary-card">
          <span>已否决</span>
          <strong class="text-red">{{ stats.rejected_count || 0 }}</strong>
          <small>人工判定不成立</small>
        </article>
        <article class="summary-card">
          <span>平均置信度</span>
          <strong>{{ stats.avg_confidence || avgConfidence }}</strong>
          <small>候选整体可信度</small>
        </article>
      </section>

      <!-- 主内容区：表格 + 详情 + 批量操作 -->
      <div class="main-layout">
        <!-- 左侧：候选表格 -->
        <section class="candidates-panel">
          <h3>新岗位候选</h3>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style="width:30px"><input type="checkbox" @change="toggleAll" v-model="allSelected" /></th>
                  <th>候选新岗位</th>
                  <th>标准化 ID</th>
                  <th>置信度</th>
                  <th>判定依据</th>
                  <th>状态</th>
                  <th style="width:140px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in candidates" :key="c.candidate_id" :class="{ selected: selectedId === c.candidate_id }">
                  <td><input type="checkbox" :value="c.candidate_id" v-model="selectedIds" /></td>
                  <td>
                    <a href="#" @click.prevent="selectCandidate(c)">{{ c.name }}</a>
                  </td>
                  <td><code>{{ c.standardized_id }}</code></td>
                  <td>
                    <div class="confidence-cell">
                      <div class="conf-bar">
                        <div class="conf-fill" :style="{ width: (c.emergence_confidence * 100) + '%', background: confColor(c.emergence_confidence) }"></div>
                      </div>
                      <span class="conf-num">{{ (c.emergence_confidence * 100).toFixed(0) }}%</span>
                    </div>
                  </td>
                  <td>
                    <span class="badge" v-for="e in c.evidence_chain?.slice(0, 2)" :key="e.type" :title="e.description">
                      {{ evidenceLabel(e.type) }}
                    </span>
                  </td>
                  <td>
                    <span :class="['status-tag', c.status]">{{ statusLabel(c.status) }}</span>
                  </td>
                  <td class="actions-cell">
                    <button class="mini-btn adopt" v-if="c.status === 'pending'" @click="adoptOne(c)">采纳</button>
                    <button class="mini-btn reject" v-if="c.status === 'pending'" @click="rejectOne(c)">否决</button>
                    <button class="mini-btn view" @click="selectCandidate(c)">详情</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 右侧：批量操作 -->
        <aside class="batch-panel">
          <h3>批量操作</h3>
          <p class="hint">已选 <strong>{{ selectedIds.length }}</strong> 个候选</p>
          <button class="primary-button full-width" :disabled="!selectedIds.length" @click="batchAdopt">确认采纳已选新岗位</button>
          <button class="primary-button full-width outline" :disabled="!selectedIds.length" @click="batchAdoptHighConf">一键采纳所有高置信度</button>
          <button class="danger-button full-width" :disabled="!selectedIds.length" @click="batchReject">否决已选候选新岗位</button>
          <button class="ghost-button full-width" @click="exportReport">导出候选报告</button>
          <button class="ghost-button full-width" @click="loadAdoptionHistory">查看采纳历史</button>

          <hr />

          <h4>置信度分布</h4>
          <div class="distro-bars">
            <div v-for="d in confidenceDistribution" :key="d.label" class="distro-row">
              <span class="distro-label">{{ d.label }}</span>
              <div class="distro-bar"><div class="distro-fill" :style="{ width: d.pct + '%' }"></div></div>
              <span class="distro-count">{{ d.count }}</span>
            </div>
          </div>
        </aside>
      </div>

      <!-- 底部：详情面板 -->
      <section v-if="detail" class="detail-panel">
        <h3>新岗位详情</h3>
        <div class="detail-grid">
          <div class="detail-main">
            <div class="detail-row">
              <span class="detail-label">岗位名称</span>
              <span class="detail-value strong">{{ detail.name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">标准化 ID</span>
              <code>{{ detail.standardized_id }}</code>
            </div>
            <div class="detail-row">
              <span class="detail-label">新兴技能</span>
              <span class="detail-value">
                <span class="skill-tag" v-for="sk in detail.emerging_skills" :key="sk">{{ sk }}</span>
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">来自现有岗位分化</span>
              <span class="detail-value">
                <code v-for="dj in detail.derived_from" :key="dj" class="from-job">{{ dj }}</code>
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">推测出现时间</span>
              <span class="detail-value">{{ detail.estimated_emergence }} <small>(置信度 {{ (detail.emergence_confidence * 100).toFixed(0) }}%)</small></span>
            </div>
            <div class="detail-row">
              <span class="detail-label">新岗位描述</span>
              <span class="detail-value">{{ detail.description }}</span>
            </div>
          </div>
          <div class="detail-evidence">
            <h4>判定证据链</h4>
            <div class="evidence-timeline">
              <div v-for="(ev, i) in detail.evidence_chain" :key="i" class="evidence-node">
                <div class="evidence-dot"></div>
                <div class="evidence-body">
                  <strong>{{ evidenceLabel(ev.type) }}</strong>
                  <p>{{ ev.description }}</p>
                  <span class="evidence-conf">置信度 {{ (ev.confidence * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <!-- 采纳历史弹窗 -->
    <div v-if="showHistory" class="modal-backdrop" @click.self="showHistory = false">
      <div class="modal">
        <h3>采纳历史</h3>
        <table>
          <thead><tr><th>候选</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="h in historyList" :key="h.candidate_id">
              <td>{{ h.name }}</td>
              <td><span :class="['status-tag', h.status]">{{ statusLabel(h.status) }}</span></td>
            </tr>
          </tbody>
        </table>
        <button class="primary-button" @click="showHistory = false">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import jobsApi from '../api/jobs'

const filters = ref({ min_confidence: 0.5, max_candidates: 20 })
const candidates = ref([])
const stats = ref({})
const loading = ref(false)
const error = ref('')
const selectedId = ref('')
const detail = ref(null)
const selectedIds = ref([])
const allSelected = ref(false)
const showHistory = ref(false)
const historyList = ref([])

const avgConfidence = computed(() => {
  if (!candidates.value.length) return 0
  const sum = candidates.value.reduce((a, c) => a + c.emergence_confidence, 0)
  return (sum / candidates.value.length).toFixed(2)
})

const confidenceDistribution = computed(() => {
  const buckets = [
    { label: '90-100%', min: 0.9, count: 0 },
    { label: '70-90%', min: 0.7, max: 0.9, count: 0 },
    { label: '50-70%', min: 0.5, max: 0.7, count: 0 },
    { label: '<50%', max: 0.5, count: 0 },
  ]
  candidates.value.forEach(c => {
    for (const b of buckets) {
      if ((b.min === undefined || c.emergence_confidence >= b.min) && (b.max === undefined || c.emergence_confidence < b.max)) {
        b.count++
        break
      }
    }
  })
  const max = Math.max(...buckets.map(b => b.count), 1)
  return buckets.map(b => ({ ...b, pct: Math.round((b.count / max) * 100) }))
})

function evidenceLabel(type) {
  const map = {
    skill_divergence: '技能偏离',
    new_skill_emergence: '新技能涌现',
    jd_frequency_surge: 'JD激增',
    industry_spread: '行业扩散',
  }
  return map[type] || type
}

function statusLabel(s) {
  const map = { pending: '待审核', adopted: '已采纳', rejected: '已否决' }
  return map[s] || s
}

function confColor(v) {
  if (v >= 0.8) return '#16a34a'
  if (v >= 0.6) return '#f59e0b'
  if (v >= 0.5) return '#f97316'
  return '#ef4444'
}

async function runDiscovery() {
  loading.value = true
  error.value = ''
  try {
    const res = await jobsApi.discoverNewJobs(filters.value)
    candidates.value = res.data.candidates || []
    stats.value = { total_candidates: res.data.total_scanned_jobs || candidates.value.length }
    detail.value = null
    selectedId.value = ''
  } catch (e) {
    error.value = '发现分析失败：' + (e.response?.data?.detail || e.message)
  } finally {
    loading.value = false
  }
}

function selectCandidate(c) {
  selectedId.value = c.candidate_id
  detail.value = c
}

function toggleAll() {
  if (allSelected.value) {
    selectedIds.value = candidates.value.filter(c => c.status === 'pending').map(c => c.candidate_id)
  } else {
    selectedIds.value = []
  }
}

async function adoptOne(c) {
  try {
    await jobsApi.adoptCandidate(c.candidate_id, true)
    c.status = 'adopted'
    if (detail.value?.candidate_id === c.candidate_id) detail.value.status = 'adopted'
  } catch (e) {
    error.value = '采纳失败：' + (e.response?.data?.detail || e.message)
  }
}

async function rejectOne(c) {
  try {
    await jobsApi.rejectCandidate(c.candidate_id)
    c.status = 'rejected'
    if (detail.value?.candidate_id === c.candidate_id) detail.value.status = 'rejected'
  } catch (e) {
    error.value = '否决失败：' + (e.response?.data?.detail || e.message)
  }
}

async function batchAdopt() {
  try {
    const res = await jobsApi.batchAdopt({ candidate_ids: selectedIds.value, create_graph_nodes: true })
    selectedIds.value.forEach(id => {
      const c = candidates.value.find(x => x.candidate_id === id)
      if (c) c.status = 'adopted'
    })
    selectedIds.value = []
    alert(res.data.summary)
  } catch (e) {
    error.value = '批量采纳失败：' + (e.response?.data?.detail || e.message)
  }
}

async function batchAdoptHighConf() {
  const highIds = candidates.value.filter(c => c.status === 'pending' && c.emergence_confidence >= 0.8).map(c => c.candidate_id)
  if (!highIds.length) { alert('没有高置信度（≥80%）的待审核候选'); return }
  try {
    const res = await jobsApi.batchAdopt({ candidate_ids: highIds, create_graph_nodes: true })
    highIds.forEach(id => {
      const c = candidates.value.find(x => x.candidate_id === id)
      if (c) c.status = 'adopted'
    })
    alert(res.data.summary)
  } catch (e) {
    error.value = '批量采纳失败：' + (e.response?.data?.detail || e.message)
  }
}

async function batchReject() {
  if (!confirm('确定否决选中的候选新岗位？')) return
  try {
    const res = await jobsApi.batchReject({ candidate_ids: selectedIds.value })
    selectedIds.value.forEach(id => {
      const c = candidates.value.find(x => x.candidate_id === id)
      if (c) c.status = 'rejected'
    })
    selectedIds.value = []
    alert(res.data.summary)
  } catch (e) {
    error.value = '批量否决失败：' + (e.response?.data?.detail || e.message)
  }
}

function exportReport() {
  const rows = [['候选新岗位', '标准化ID', '置信度', '推测时间', '状态', '新兴技能', '来源岗位', '描述']]
  candidates.value.forEach(c => {
    rows.push([c.name, c.standardized_id, c.emergence_confidence.toFixed(2), c.estimated_emergence, c.status, c.emerging_skills.join(';'), c.derived_from.join(';'), c.description])
  })
  const csv = rows.map(r => r.map(x => '"' + String(x).replace(/"/g, '""') + '"').join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'new_job_candidates.csv'; a.click()
  URL.revokeObjectURL(url)
}

async function loadAdoptionHistory() {
  try {
    const res = await jobsApi.getAdoptionHistory()
    historyList.value = res.data.history || []
    showHistory.value = true
  } catch (e) {
    error.value = '加载历史失败：' + (e.response?.data?.detail || e.message)
  }
}
</script>

<style scoped>
/* 复用项目通用样式 */
.page { max-width: 1300px; }
.page-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.page-heading h2 { margin: 0; color: #0f172a; }
.eyebrow { margin: 0 0 4px; color: #2563eb; font-size: 11px; font-weight: 800; letter-spacing: .15em; }
.page-heading p { margin: 4px 0 0; color: #64748b; font-size: 13px; }

.filters { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 20px; background: #fff; padding: 16px 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.filters label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #64748b; }
.filters input, .filters select { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 13px; min-width: 120px; }
.primary-button { padding: 8px 20px; background: #2563eb; color: #fff; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .2s; }
.primary-button:hover:not(:disabled) { background: #1d4ed8; }
.primary-button:disabled { opacity: .5; cursor: not-allowed; }
.primary-button.outline { background: #fff; color: #2563eb; border: 1px solid #2563eb; }
.danger-button { padding: 8px 20px; background: #fff; color: #dc2626; border: 1px solid #fca5a5; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
.danger-button:hover:not(:disabled) { background: #fef2f2; }
.danger-button:disabled { opacity: .5; cursor: not-allowed; }
.ghost-button { padding: 8px 20px; background: transparent; color: #64748b; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 13px; cursor: pointer; }
.ghost-button:hover { background: #f8fafc; }
.full-width { width: 100%; margin-bottom: 8px; }

.message { padding: 40px; text-align: center; color: #64748b; background: #fff; border-radius: 12px; }
.error-message { color: #dc2626; background: #fef2f2; }

.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
.summary-card { background: #fff; padding: 16px 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.summary-card span { display: block; font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .08em; }
.summary-card strong { display: block; font-size: 28px; margin: 4px 0; }
.summary-card small { font-size: 11px; color: #94a3b8; }
.text-green { color: #16a34a; }
.text-red { color: #dc2626; }

.main-layout { display: grid; grid-template-columns: 1fr 260px; gap: 20px; margin-bottom: 20px; }

.candidates-panel { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); padding: 20px; }
.candidates-panel h3 { margin: 0 0 12px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 10px 8px; border-bottom: 2px solid #e2e8f0; color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; }
td { padding: 10px 8px; border-bottom: 1px solid #f1f5f9; }
tr.selected { background: #eff6ff; }
td a { color: #2563eb; text-decoration: none; font-weight: 600; }
td a:hover { text-decoration: underline; }
td code { font-size: 11px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }

.confidence-cell { display: flex; align-items: center; gap: 8px; min-width: 110px; }
.conf-bar { width: 70px; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
.conf-fill { height: 100%; border-radius: 3px; transition: width .3s; }
.conf-num { font-size: 12px; font-weight: 600; color: #475569; }

.badge { display: inline-block; padding: 2px 8px; margin: 1px 2px; background: #eff6ff; color: #2563eb; border-radius: 4px; font-size: 10px; font-weight: 500; white-space: nowrap; }
.status-tag { display: inline-block; padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.status-tag.pending { background: #fef3c7; color: #92400e; }
.status-tag.adopted { background: #dcfce7; color: #166534; }
.status-tag.rejected { background: #fee2e2; color: #991b1b; }

.actions-cell { white-space: nowrap; }
.mini-btn { padding: 4px 10px; margin: 1px 2px; border-radius: 6px; font-size: 11px; cursor: pointer; border: 1px solid transparent; font-weight: 500; }
.mini-btn.adopt { background: #16a34a; color: #fff; border-color: #16a34a; }
.mini-btn.adopt:hover { background: #15803d; }
.mini-btn.reject { background: #fff; color: #dc2626; border-color: #fca5a5; }
.mini-btn.reject:hover { background: #fef2f2; }
.mini-btn.view { background: #fff; color: #2563eb; border-color: #cbd5e1; }
.mini-btn.view:hover { background: #f8fafc; }

.batch-panel { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); padding: 20px; }
.batch-panel h3, .batch-panel h4 { margin: 0 0 8px; }
.batch-panel hr { margin: 16px 0; border: none; border-top: 1px solid #e2e8f0; }
.hint { font-size: 12px; color: #64748b; margin: 0 0 12px; }

.distro-bars { font-size: 12px; }
.distro-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.distro-label { width: 55px; color: #64748b; font-size: 11px; }
.distro-bar { flex: 1; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; }
.distro-fill { height: 100%; background: #2563eb; border-radius: 4px; }
.distro-count { width: 20px; text-align: right; font-weight: 600; color: #475569; }

.detail-panel { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); padding: 24px; }
.detail-panel h3 { margin: 0 0 16px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.detail-row { margin-bottom: 14px; }
.detail-label { display: block; font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px; }
.detail-value { font-size: 14px; color: #1e293b; }
.detail-value.strong { font-size: 18px; font-weight: 700; }
.detail-value small { font-size: 12px; color: #94a3b8; }
.from-job { margin-right: 8px; }

.skill-tag { display: inline-block; padding: 3px 10px; margin: 2px 4px 2px 0; background: #dbeafe; color: #1e40af; border-radius: 10px; font-size: 12px; }

.detail-evidence h4 { margin: 0 0 12px; }
.evidence-timeline { border-left: 2px solid #e2e8f0; padding-left: 16px; }
.evidence-node { position: relative; margin-bottom: 14px; }
.evidence-dot { position: absolute; left: -21px; top: 4px; width: 8px; height: 8px; border-radius: 50%; background: #2563eb; }
.evidence-body strong { font-size: 13px; color: #1e293b; }
.evidence-body p { margin: 3px 0; font-size: 12px; color: #64748b; }
.evidence-conf { font-size: 11px; color: #94a3b8; }

.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 16px; padding: 24px; max-width: 500px; width: 90%; max-height: 70vh; overflow-y: auto; }
.modal h3 { margin: 0 0 12px; }

@media (max-width: 900px) {
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
  .main-layout { grid-template-columns: 1fr; }
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
