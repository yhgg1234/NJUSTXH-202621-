<template>
  <div class="page">
    <header class="hero">
      <div class="hero-copy">
        <p class="eyebrow">LABOR MARKET INTELLIGENCE</p>
        <h2>岗位趋势洞察</h2>
        <p>融合多源招聘需求与岗位知识图谱，识别新兴岗位并持续追踪能力结构变化。</p>
      </div>
      <label class="reviewer">
        <span>评审人</span>
        <input v-model.trim="reviewer" aria-label="评审人" />
      </label>
    </header>

    <nav class="view-tabs" aria-label="岗位趋势分析视图">
      <button type="button" :class="{ active: activeView === 'discovery' }" @click="activeView = 'discovery'">
        <span class="tab-icon">✦</span>
        <span><strong>新兴岗位识别</strong><small>发现市场中的新岗位形态</small></span>
      </button>
      <button type="button" :class="{ active: activeView === 'changes' }" @click="activeView = 'changes'">
        <span class="tab-icon">↗</span>
        <span><strong>能力变化监测</strong><small>追踪岗位能力需求变化</small></span>
      </button>
    </nav>

    <div v-if="error" class="message error-message">{{ error }}</div>

    <template v-if="activeView === 'discovery'">
      <section class="panel filter-panel">
        <div class="section-heading">
          <div>
            <h3>设置识别范围</h3>
            <p>可按时间和样本覆盖要求筛选，系统将自动完成聚类、趋势计算与图谱比对。</p>
          </div>
          <span class="data-badge"><i></i> 多源数据就绪</span>
        </div>
        <form class="filters" @submit.prevent="runDiscovery">
          <label><span>开始日期</span><input v-model="filters.start" type="date" /></label>
          <label><span>结束日期</span><input v-model="filters.end" type="date" /></label>
          <label><span>新颖度阈值</span><input v-model.number="filters.novelty_threshold" type="number" min="0" max="1" step="0.05" /></label>
          <label><span>最少有效样本</span><input v-model.number="filters.min_frequency" type="number" min="1" /></label>
          <label><span>最少企业覆盖</span><input v-model.number="filters.min_companies" type="number" min="1" /></label>
          <label><span>最少数据来源</span><input v-model.number="filters.min_sources" type="number" min="1" /></label>
          <button class="primary-button" :disabled="loading">{{ loading ? '正在分析…' : '开始智能识别' }}</button>
        </form>
      </section>

      <div v-if="quality.warnings?.length" class="quality-warning">
        <strong>数据质量提示</strong>
        <ul><li v-for="item in quality.warnings" :key="item">{{ item }}</li></ul>
      </div>

      <section class="summary-grid">
        <article class="metric-card primary"><span>发现候选</span><strong>{{ stats.total_candidates || 0 }}</strong><small>新兴岗位形态</small></article>
        <article class="metric-card success"><span>已确认</span><strong>{{ stats.adopted_count || 0 }}</strong><small>纳入岗位知识库</small></article>
        <article class="metric-card muted"><span>已排除</span><strong>{{ stats.rejected_count || 0 }}</strong><small>不满足确认条件</small></article>
        <article class="metric-card"><span>有效招聘样本</span><strong>{{ quality.valid_records || 0 }}</strong><small>通过质量校验</small></article>
        <article class="metric-card"><span>知识库参照岗位</span><strong>{{ scanStats.jobs || 0 }}</strong><small>参与相似度比对</small></article>
      </section>

      <section class="panel result-panel">
        <div class="panel-title">
          <div><h3>新兴岗位候选</h3><p>候选结果均保留来源、趋势和技能组合证据，确认后可纳入岗位知识库。</p></div>
          <div class="batch-actions">
            <span>已选择 {{ selectedIds.length }} 项</span>
            <button type="button" :disabled="!selectedIds.length" @click="batchAdopt">批量确认</button>
            <button type="button" :disabled="!selectedIds.length" class="danger" @click="batchReject">批量排除</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th></th><th>岗位名称</th><th>样本覆盖</th><th>新颖程度</th><th>增长势能</th><th>可信度</th><th>评审状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="candidate in candidates" :key="candidate.candidate_id">
                <td><input v-model="selectedIds" :value="candidate.candidate_id" type="checkbox" :disabled="candidate.status !== 'pending'" /></td>
                <td><a href="#" @click.prevent="selectCandidate(candidate)">{{ candidate.name }}</a><small>{{ candidate.standardized_id }}</small></td>
                <td>{{ candidate.supporting_jd_count }} 条招聘信息<br><small>{{ candidate.company_count }} 家企业 · {{ candidate.source_count }} 个来源</small></td>
                <td>{{ percent(candidate.novelty_score) }}</td>
                <td>{{ percent(candidate.trend_score) }}</td>
                <td><div class="confidence"><progress max="1" :value="candidate.emergence_confidence"></progress><span>{{ percent(candidate.emergence_confidence) }}</span></div></td>
                <td><span :class="['status', candidate.status]">{{ statusLabel(candidate.status) }}</span></td>
                <td><button type="button" class="text-button" @click="selectCandidate(candidate)">查看详情</button></td>
              </tr>
              <tr v-if="!candidates.length"><td colspan="8" class="empty"><span class="empty-icon">⌁</span><strong>暂无识别结果</strong><small>设置分析范围后点击“开始智能识别”，结果将在这里展示</small></td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="detail" class="panel detail-panel">
        <div class="panel-title">
          <div><p class="detail-kicker">候选岗位详情</p><h3>{{ detail.name }}</h3></div>
          <div class="detail-actions">
            <button v-if="detail.status === 'pending'" type="button" @click="startEdit">编辑岗位定义</button>
            <button v-if="detail.status === 'pending'" type="button" class="primary-button" @click="adoptOne">确认并纳入知识库</button>
            <button v-if="detail.status === 'pending'" type="button" class="danger" @click="rejectOne">排除候选</button>
          </div>
        </div>

        <form v-if="editing" class="edit-form" @submit.prevent="saveEdit">
          <label><span>岗位名称</span><input v-model="edit.name" required /></label>
          <label><span>岗位定义</span><textarea v-model="edit.description" rows="4" required></textarea></label>
          <label><span>核心职责（每行一项）</span><textarea v-model="edit.responsibilities" rows="5"></textarea></label>
          <label><span>典型行业场景（每行一项）</span><textarea v-model="edit.industries" rows="4"></textarea></label>
          <label><span>必备技能明细（高级编辑）</span><textarea v-model="edit.requiredSkills" rows="8"></textarea></label>
          <label><span>加分技能明细（高级编辑）</span><textarea v-model="edit.bonusSkills" rows="8"></textarea></label>
          <label><span>调整说明</span><input v-model="edit.comment" /></label>
          <div><button class="primary-button">保存调整</button><button type="button" @click="editing = false">取消</button></div>
        </form>

        <template v-else>
          <div class="definition-grid">
            <div>
              <p class="description">{{ detail.description }}</p>
              <h5>核心职责</h5><ul><li v-for="item in detail.core_responsibilities" :key="item">{{ item }}</li></ul>
              <h5>典型应用场景</h5><div><span v-for="item in detail.industry_scenarios" :key="item" class="tag industry">{{ item }}</span></div>
            </div>
            <div class="skill-card">
              <h5>核心能力要求</h5>
              <div class="skill-list"><span v-for="skill in detail.required_skills" :key="skill.id" class="tag required" :title="skill.id">{{ skill.name }} · {{ percent(skill.support_ratio) }}</span></div>
              <h5>拓展能力要求</h5>
              <div class="skill-list"><span v-for="skill in detail.bonus_skills" :key="skill.id" class="tag bonus" :title="skill.id">{{ skill.name }} · {{ percent(skill.support_ratio) }}</span></div>
              <p class="meta">首次出现 {{ detail.estimated_emergence }}<br>最新观测 {{ detail.latest_period }}<br>最相近岗位 {{ detail.closest_existing_job_name }}（{{ percent(detail.closest_similarity) }}）</p>
            </div>
          </div>
          <h5 class="evidence-title">判定依据</h5>
          <div class="evidence-grid">
            <article v-for="evidence in detail.evidence_chain" :key="evidence.type">
              <strong>{{ evidenceLabel(evidence.type) }}</strong><p>{{ evidence.description }}</p><small>可信度 {{ percent(evidence.confidence) }} · {{ evidence.supporting_ids.length }} 条来源记录</small>
            </article>
          </div>
        </template>
      </section>
    </template>

    <template v-else>
      <section class="panel change-panel">
        <div class="section-heading">
          <div><h3>岗位能力变化监测</h3><p>比较不同观察周期的岗位画像，识别新增、减弱或消失的能力要求。</p></div>
          <span class="data-badge"><i></i> 知识图谱已连接</span>
        </div>
        <form class="filters change-filters" @submit.prevent="analyzeChanges">
          <label class="wide"><span>岗位标识</span><input v-model.trim="changeQuery.job_id" required placeholder="例如：job:backend-engineer" /></label>
          <label><span>基准周期</span><input v-model.trim="changeQuery.from_period" required placeholder="例如：2025Q1" /></label>
          <label><span>对比周期</span><input v-model.trim="changeQuery.to_period" required placeholder="例如：2025Q2" /></label>
          <label><span>显著变化阈值</span><input v-model.number="changeQuery.change_threshold" type="number" min="0" max="1" step="0.01" /></label>
          <button class="primary-button">生成变化分析</button>
        </form>
      </section>
      <div v-if="changeWarnings.length" class="quality-warning">{{ changeWarnings.join('；') }}</div>
      <section class="panel result-panel">
        <div class="panel-title"><div><h3>能力变化明细</h3><p>每项变化均保留对应的招聘数据证据，可进行人工复核。</p></div></div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>能力项</th><th>变化类型</th><th>基准周期</th><th>对比周期</th><th>变化幅度</th><th>证据数量</th><th>复核状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="change in changes" :key="change.change_id">
                <td>{{ change.entity_name }}<small>{{ change.entity_id }}</small></td>
                <td>{{ changeTypeLabel(change.change_type) }}</td>
                <td>{{ ratioOf(change.before) }}</td><td>{{ ratioOf(change.after) }}</td><td>{{ signed(change.delta) }}</td>
                <td>{{ change.evidence_ids.length }} 条</td><td>{{ reviewLabel(change.review_status) }}</td>
                <td><button type="button" class="text-button" @click="reviewChange(change, 'approved')">确认</button><button type="button" class="text-button danger-text" @click="reviewChange(change, 'rejected')">驳回</button></td>
              </tr>
              <tr v-if="!changes.length"><td colspan="8" class="empty"><span class="empty-icon">↗</span><strong>暂无变化分析</strong><small>选择岗位与对比周期后，系统将呈现能力结构变化</small></td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import jobsApi from '../api/jobs'

const reviewer = ref('人工审核员')
const activeView = ref('discovery')
const filters = reactive({ start: '', end: '', novelty_threshold: 0.3, min_frequency: 5, min_companies: 2, min_sources: 2 })
const candidates = ref([])
const selectedIds = ref([])
const detail = ref(null)
const stats = ref({})
const scanStats = reactive({ jobs: 0, skills: 0, records: 0 })
const quality = ref({ warnings: [] })
const loading = ref(false)
const error = ref('')
const editing = ref(false)
const edit = reactive({ name: '', description: '', responsibilities: '', industries: '', requiredSkills: '[]', bonusSkills: '[]', comment: '' })
const changeQuery = reactive({ job_id: 'job:backend-engineer', from_period: '2025Q1', to_period: '2025Q2', granularity: 'quarterly', change_threshold: 0.05 })
const changes = ref([])
const changeWarnings = ref([])

onMounted(refreshStats)

async function refreshStats() {
  try { stats.value = (await jobsApi.getDiscoverStats()).data || {} } catch (_) { stats.value ||= {} }
}

async function runDiscovery() {
  loading.value = true; error.value = ''
  try {
    const payload = { novelty_threshold: filters.novelty_threshold, min_frequency: filters.min_frequency, min_companies: filters.min_companies, min_sources: filters.min_sources }
    if (filters.start && filters.end) payload.time_range = [filters.start, filters.end]
    const { data } = await jobsApi.discoverNewJobs(payload)
    candidates.value = data.candidates || []
    quality.value = data.data_quality || { warnings: [] }
    scanStats.jobs = data.total_scanned_jobs; scanStats.skills = data.total_scanned_skills; scanStats.records = data.total_scanned_records
    selectedIds.value = []; detail.value = null
    await refreshStats()
  } catch (e) { error.value = errorMessage(e, '发现分析失败') }
  finally { loading.value = false }
}

function selectCandidate(candidate) { detail.value = candidate; editing.value = false }
function startEdit() {
  edit.name = detail.value.name; edit.description = detail.value.description
  edit.responsibilities = detail.value.core_responsibilities.join('\n'); edit.industries = detail.value.industry_scenarios.join('\n')
  edit.requiredSkills = JSON.stringify(detail.value.required_skills, null, 2); edit.bonusSkills = JSON.stringify(detail.value.bonus_skills, null, 2)
  edit.comment = ''; editing.value = true
}
async function saveEdit() {
  try {
    const payload = { name: edit.name, description: edit.description, core_responsibilities: lines(edit.responsibilities), industry_scenarios: lines(edit.industries), required_skills: JSON.parse(edit.requiredSkills), bonus_skills: JSON.parse(edit.bonusSkills), reviewer: reviewer.value, review_comment: edit.comment }
    const { data } = await jobsApi.editCandidate(detail.value.candidate_id, payload)
    replaceCandidate(data); detail.value = data; editing.value = false
  } catch (e) { error.value = errorMessage(e, '保存人工优化失败') }
}
async function adoptOne() {
  if (!confirm('确认岗位定义无误并纳入岗位知识库？')) return
  try { await jobsApi.adoptCandidate(detail.value.candidate_id, { reviewer: reviewer.value, comment: '人工审核通过', create_graph_nodes: true }); detail.value.status = 'adopted'; replaceCandidate(detail.value); await refreshStats() }
  catch (e) { error.value = errorMessage(e, '采纳失败') }
}
async function rejectOne() {
  const comment = prompt('请输入否决原因：', '')
  if (comment === null) return
  try { await jobsApi.rejectCandidate(detail.value.candidate_id, { reviewer: reviewer.value, comment, create_graph_nodes: false }); detail.value.status = 'rejected'; replaceCandidate(detail.value); await refreshStats() }
  catch (e) { error.value = errorMessage(e, '否决失败') }
}
async function batchAdopt() {
  try { await jobsApi.batchAdopt({ candidate_ids: selectedIds.value, create_graph_nodes: true, reviewer: reviewer.value, comment: '批量人工审核通过' }); markSelected('adopted'); await refreshStats() }
  catch (e) { error.value = errorMessage(e, '批量采纳失败') }
}
async function batchReject() {
  const comment = prompt('请输入批量否决原因：', '')
  if (comment === null) return
  try { await jobsApi.batchReject({ candidate_ids: selectedIds.value, reviewer: reviewer.value, comment }); markSelected('rejected'); await refreshStats() }
  catch (e) { error.value = errorMessage(e, '批量否决失败') }
}
function markSelected(status) { candidates.value.forEach(item => { if (selectedIds.value.includes(item.candidate_id)) item.status = status }); selectedIds.value = [] }
function replaceCandidate(value) { const index = candidates.value.findIndex(item => item.candidate_id === value.candidate_id); if (index >= 0) candidates.value[index] = value }

async function analyzeChanges() {
  error.value = ''
  try { const { data } = await jobsApi.analyzeAbilityChanges({ ...changeQuery }); changes.value = data.changes || []; changeWarnings.value = data.warnings || [] }
  catch (e) { error.value = errorMessage(e, '能力变化分析失败') }
}
async function reviewChange(change, status) {
  const comment = prompt(status === 'approved' ? '审核说明：' : '驳回原因：', '')
  if (comment === null) return
  try { const { data } = await jobsApi.reviewAbilityChange(change.change_id, { status, reviewer: reviewer.value, comment }); Object.assign(change, data) }
  catch (e) { error.value = errorMessage(e, '变更审核失败') }
}

function lines(value) { return value.split(/\r?\n/).map(item => item.trim()).filter(Boolean) }
function percent(value) { return `${((Number(value) || 0) * 100).toFixed(1)}%` }
function signed(value) { const number = Number(value) || 0; return `${number > 0 ? '+' : ''}${number.toFixed(4)}` }
function ratioOf(value) { return value ? percent(value.demand_ratio) : '—' }
function statusLabel(value) { return ({ pending: '待审核', adopted: '已采纳', rejected: '已否决' })[value] || value }
function reviewLabel(value) { return ({ pending: '待审核', approved: '已通过', rejected: '已驳回' })[value] || value }
function changeTypeLabel(value) { return ({ added: '新增', removed: '删除', increased: '增强', decreased: '减弱', renamed: '改名', merged: '合并', split: '拆分' })[value] || value }
function evidenceLabel(value) { return ({ community_cluster: '技能群落特征', skill_novelty: '技能组合差异', jd_frequency_surge: '招聘需求增长', multi_source_support: '多源交叉验证' })[value] || value }
function errorMessage(error, prefix) { const detail = error.response?.data?.detail; return `${prefix}：${typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : error.message}` }
</script>

<style scoped>
.page { max-width: 1400px; animation: fadeIn .25s ease; }
.hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 28px; margin-bottom: 22px; }
.hero-copy h2 { margin: 4px 0 8px; color: #0f172a; font-size: 28px; letter-spacing: -.025em; }
.hero-copy > p:last-child { max-width: 700px; margin: 0; color: #64748b; font-size: 14px; line-height: 1.65; }
.eyebrow { margin: 0; color: #2563eb; font-size: 10px; font-weight: 800; letter-spacing: .18em; }
.reviewer { width: 180px; color: #64748b; font-size: 12px; }
.reviewer span, .filters label span, .edit-form label span { display: block; margin-bottom: 6px; color: #475569; font-size: 12px; font-weight: 650; }
input, textarea { width: 100%; border: 1px solid #cbd5e1; border-radius: 9px; padding: 9px 11px; color: #0f172a; background: #fff; font: inherit; transition: border-color .2s, box-shadow .2s; }
input:focus, textarea:focus { border-color: #2563eb; outline: 0; box-shadow: 0 0 0 3px rgba(37,99,235,.11); }
.view-tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; max-width: 700px; margin-bottom: 18px; padding: 5px; border: 1px solid #e2e8f0; border-radius: 14px; background: rgba(255,255,255,.72); }
.view-tabs button { display: flex; align-items: center; gap: 11px; border: 0; border-radius: 10px; padding: 11px 15px; color: #64748b; background: transparent; text-align: left; cursor: pointer; }
.view-tabs button.active { color: #1d4ed8; background: #fff; box-shadow: 0 3px 12px rgba(15,23,42,.08); }
.view-tabs strong, .view-tabs small { display: block; }.view-tabs strong { font-size: 13px; }.view-tabs small { margin-top: 3px; color: #94a3b8; font-size: 10px; }.tab-icon { display: grid; width: 29px; height: 29px; place-items: center; border-radius: 8px; color: #2563eb; background: #eff6ff; font-size: 16px; }
.panel { margin-bottom: 16px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px; background: #fff; box-shadow: 0 5px 22px rgba(15,23,42,.045); }
.filter-panel { padding: 20px 22px; background: linear-gradient(145deg,#fff 40%,#f8fbff); }
.section-heading, .panel-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.section-heading h3, .panel-title h3 { margin: 0 0 5px; color: #0f172a; font-size: 16px; }
.section-heading p, .panel-title p { margin: 0; color: #64748b; font-size: 12px; line-height: 1.55; }
.data-badge { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 7px; padding: 6px 10px; border-radius: 999px; color: #047857; background: #ecfdf5; font-size: 11px; font-weight: 700; }.data-badge i { width: 6px; height: 6px; border-radius: 50%; background: #10b981; box-shadow: 0 0 0 4px rgba(16,185,129,.12); }
.filters { display: grid; grid-template-columns: repeat(6,minmax(105px,1fr)) auto; gap: 12px; align-items: end; }.filters label { min-width: 0; }.filters .wide { min-width: 210px; }
button { border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 12px; color: #334155; background: #fff; font: inherit; cursor: pointer; transition: .18s ease; }button:hover:not(:disabled) { border-color: #93c5fd; color: #1d4ed8; background: #f8fbff; }button:disabled { cursor: not-allowed; opacity: .42; }
.primary-button { min-height: 38px; border-color: #2563eb; color: #fff; background: #2563eb; font-weight: 700; box-shadow: 0 4px 10px rgba(37,99,235,.18); }.primary-button:hover:not(:disabled) { border-color: #1d4ed8; color: #fff; background: #1d4ed8; }
.danger { border-color: #fecaca; color: #b91c1c; }.danger:hover:not(:disabled) { border-color: #fca5a5; color: #991b1b; background: #fef2f2; }
.message, .quality-warning { margin-bottom: 16px; padding: 13px 16px; border-radius: 11px; }.error-message { color: #b91c1c; background: #fef2f2; }.quality-warning { border: 1px solid #fde68a; color: #92400e; background: #fffbeb; }.quality-warning ul { margin: 6px 0 0; padding-left: 19px; }
.summary-grid { display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); gap: 12px; margin-bottom: 16px; }.metric-card { position: relative; min-height: 112px; overflow: hidden; padding: 17px 18px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; }.metric-card::after { position: absolute; right: -16px; bottom: -22px; width: 72px; height: 72px; border-radius: 50%; background: #f1f5f9; content: ''; }.metric-card.primary::after { background: #dbeafe; }.metric-card.success::after { background: #d1fae5; }.metric-card.muted::after { background: #f1f5f9; }.metric-card span, .metric-card small { display: block; color: #64748b; font-size: 11px; }.metric-card strong { display: block; margin: 8px 0 4px; color: #0f172a; font-size: 27px; line-height: 1; }.metric-card.primary strong { color: #1d4ed8; }.metric-card.success strong { color: #047857; }
.result-panel { padding-bottom: 8px; }.batch-actions, .detail-actions { display: flex; align-items: center; gap: 8px; }.batch-actions span { margin-right: 2px; color: #64748b; font-size: 11px; }
.table-wrap { overflow: auto; }table { width: 100%; border-collapse: collapse; font-size: 13px; }th,td { padding: 12px 10px; border-bottom: 1px solid #edf2f7; color: #334155; text-align: left; vertical-align: middle; }th { color: #64748b; background: #f8fafc; font-size: 10px; font-weight: 750; letter-spacing: .04em; white-space: nowrap; }tbody tr { transition: background .15s; }tbody tr:not(:last-child):hover { background: #fafcff; }td small { display: block; margin-top: 4px; color: #94a3b8; font-size: 10px; }td a { color: #1d4ed8; font-weight: 700; text-decoration: none; }.text-button { border: 0; padding: 4px; color: #2563eb; background: transparent; font-weight: 650; }.danger-text { margin-left: 6px; color: #b91c1c; }.confidence { display: flex; align-items: center; gap: 7px; white-space: nowrap; }.confidence progress { width: 58px; height: 6px; accent-color: #2563eb; }
.empty { height: 165px; color: #94a3b8; text-align: center; }.empty-icon, .empty strong, .empty small { display: block; }.empty-icon { margin-bottom: 7px; color: #93c5fd; font-size: 28px; }.empty strong { color: #64748b; font-size: 13px; }.empty small { margin-top: 5px; font-size: 11px; }
.status,.tag { display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: 10px; white-space: nowrap; }.status.pending { color: #92400e; background: #fef3c7; }.status.adopted { color: #166534; background: #dcfce7; }.status.rejected { color: #991b1b; background: #fee2e2; }
.detail-panel { border-top: 3px solid #3b82f6; }.detail-kicker { margin: 0 0 3px!important; color: #2563eb!important; font-size: 10px!important; font-weight: 750; letter-spacing: .08em; }.definition-grid { display: grid; grid-template-columns: 1.25fr .75fr; gap: 32px; }.description { color: #475569; line-height: 1.7; }.definition-grid h5, .evidence-title { margin: 20px 0 9px; color: #334155; }.definition-grid ul { padding-left: 20px; color: #475569; line-height: 1.8; }.skill-card { padding: 18px; border-radius: 13px; background: #f8fafc; }.skill-card h5:first-child { margin-top: 0; }.tag { margin: 3px 5px 3px 0; }.tag.required { color: #1e40af; background: #dbeafe; }.tag.bonus { color: #6b21a8; background: #f3e8ff; }.tag.industry { color: #166534; background: #dcfce7; }.meta { margin: 18px 0 0; color: #64748b; font-size: 11px; line-height: 1.8; }.evidence-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; }.evidence-grid article { padding: 14px; border: 1px solid #e2e8f0; border-radius: 11px; }.evidence-grid strong { color: #334155; font-size: 12px; }.evidence-grid p { margin: 6px 0; color: #64748b; font-size: 12px; line-height: 1.55; }.evidence-grid small { color: #94a3b8; font-size: 10px; }
.edit-form { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; }.edit-form label:nth-child(2),.edit-form label:nth-child(5),.edit-form label:nth-child(6),.edit-form div { grid-column: 1/-1; }.edit-form div { display: flex; gap: 8px; }
.change-filters { grid-template-columns: 1.5fr repeat(3,minmax(130px,1fr)) auto; }.change-panel { padding-bottom: 22px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
@media(max-width:1100px){.filters,.change-filters{grid-template-columns:repeat(3,minmax(0,1fr))}.summary-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:780px){.hero,.section-heading,.panel-title{align-items:flex-start;flex-direction:column}.reviewer{width:100%}.view-tabs{max-width:none}.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.definition-grid,.evidence-grid,.edit-form{grid-template-columns:1fr}.batch-actions,.detail-actions{flex-wrap:wrap}}
@media(max-width:560px){.view-tabs,.filters,.change-filters,.summary-grid{grid-template-columns:1fr}.panel{padding:16px}.view-tabs small{display:none}}
</style>
