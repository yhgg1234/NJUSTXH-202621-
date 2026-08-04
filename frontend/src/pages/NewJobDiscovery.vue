<template>
  <div class="page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">TASK 2.4 · EVIDENCE-BASED DISCOVERY</p>
        <h2>新岗位发现与能力动态更新</h2>
        <p>读取 2.2 逐 JD 标准化数据，对照 2.3 图谱生成可追溯候选和能力变更日志。</p>
      </div>
      <label class="reviewer"><span>当前审核人</span><input v-model.trim="reviewer" /></label>
    </header>

    <form class="filters" @submit.prevent="runDiscovery">
      <label><span>开始日期</span><input v-model="filters.start" type="date" /></label>
      <label><span>结束日期</span><input v-model="filters.end" type="date" /></label>
      <label><span>Novelty 阈值</span><input v-model.number="filters.novelty_threshold" type="number" min="0" max="1" step="0.05" /></label>
      <label><span>最少去重 JD</span><input v-model.number="filters.min_frequency" type="number" min="1" /></label>
      <label><span>最少公司</span><input v-model.number="filters.min_companies" type="number" min="1" /></label>
      <label><span>最少渠道</span><input v-model.number="filters.min_sources" type="number" min="1" /></label>
      <button class="primary-button" :disabled="loading">{{ loading ? '分析中…' : '执行真实数据发现' }}</button>
    </form>

    <div v-if="error" class="message error-message">{{ error }}</div>
    <div v-if="quality.warnings?.length" class="quality-warning">
      <strong>数据质量提示</strong>
      <ul><li v-for="item in quality.warnings" :key="item">{{ item }}</li></ul>
    </div>

    <section class="summary-grid">
      <article><span>候选</span><strong>{{ stats.total_candidates || 0 }}</strong></article>
      <article><span>已采纳</span><strong class="green">{{ stats.adopted_count || 0 }}</strong></article>
      <article><span>已否决</span><strong class="red">{{ stats.rejected_count || 0 }}</strong></article>
      <article><span>有效 JD</span><strong>{{ quality.valid_records || 0 }}</strong></article>
      <article><span>对照岗位</span><strong>{{ scanStats.jobs || 0 }}</strong></article>
    </section>

    <section class="panel">
      <div class="panel-title">
        <h3>新岗位候选</h3>
        <div class="batch-actions">
          <span>已选 {{ selectedIds.length }}</span>
          <button :disabled="!selectedIds.length" @click="batchAdopt">批量采纳</button>
          <button :disabled="!selectedIds.length" class="danger" @click="batchReject">批量否决</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th></th><th>岗位</th><th>样本/来源</th><th>Novelty</th><th>趋势</th><th>综合置信度</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="candidate in candidates" :key="candidate.candidate_id">
              <td><input v-model="selectedIds" :value="candidate.candidate_id" type="checkbox" :disabled="candidate.status !== 'pending'" /></td>
              <td><a href="#" @click.prevent="selectCandidate(candidate)">{{ candidate.name }}</a><small>{{ candidate.standardized_id }}</small></td>
              <td>{{ candidate.supporting_jd_count }} JD / {{ candidate.company_count }} 公司 / {{ candidate.source_count }} 渠道</td>
              <td>{{ percent(candidate.novelty_score) }}</td>
              <td>{{ percent(candidate.trend_score) }}</td>
              <td><progress max="1" :value="candidate.emergence_confidence"></progress> {{ percent(candidate.emergence_confidence) }}</td>
              <td><span :class="['status', candidate.status]">{{ statusLabel(candidate.status) }}</span></td>
              <td><button @click="selectCandidate(candidate)">详情</button></td>
            </tr>
            <tr v-if="!candidates.length"><td colspan="8" class="empty">尚未执行发现，或没有达到阈值的候选。</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="detail" class="panel detail-panel">
      <div class="panel-title">
        <h3>候选定义与证据</h3>
        <div>
          <button v-if="detail.status === 'pending'" @click="startEdit">人工优化</button>
          <button v-if="detail.status === 'pending'" class="primary-button" @click="adoptOne">审核通过并写入图谱</button>
          <button v-if="detail.status === 'pending'" class="danger" @click="rejectOne">否决</button>
        </div>
      </div>

      <form v-if="editing" class="edit-form" @submit.prevent="saveEdit">
        <label><span>岗位名称</span><input v-model="edit.name" required /></label>
        <label><span>岗位定义</span><textarea v-model="edit.description" rows="4" required></textarea></label>
        <label><span>核心职责（每行一项）</span><textarea v-model="edit.responsibilities" rows="5"></textarea></label>
        <label><span>典型行业场景（每行一项）</span><textarea v-model="edit.industries" rows="4"></textarea></label>
        <label><span>必备技能 JSON</span><textarea v-model="edit.requiredSkills" rows="8"></textarea></label>
        <label><span>加分技能 JSON</span><textarea v-model="edit.bonusSkills" rows="8"></textarea></label>
        <label><span>优化说明</span><input v-model="edit.comment" /></label>
        <div><button class="primary-button">保存人工优化</button><button type="button" @click="editing = false">取消</button></div>
      </form>

      <template v-else>
        <div class="definition-grid">
          <div>
            <h4>{{ detail.name }}</h4>
            <p>{{ detail.description }}</p>
            <h5>核心职责</h5><ul><li v-for="item in detail.core_responsibilities" :key="item">{{ item }}</li></ul>
            <h5>典型行业应用场景</h5><div><span v-for="item in detail.industry_scenarios" :key="item" class="tag industry">{{ item }}</span></div>
          </div>
          <div>
            <h5>必备技能</h5>
            <div class="skill-list"><span v-for="skill in detail.required_skills" :key="skill.id" class="tag required" :title="skill.id">{{ skill.name }} {{ percent(skill.support_ratio) }}</span></div>
            <h5>加分技能</h5>
            <div class="skill-list"><span v-for="skill in detail.bonus_skills" :key="skill.id" class="tag bonus" :title="skill.id">{{ skill.name }} {{ percent(skill.support_ratio) }}</span></div>
            <p class="meta">出现时间 {{ detail.estimated_emergence }}；最新周期 {{ detail.latest_period }}；最相近岗位 {{ detail.closest_existing_job_name }}（{{ percent(detail.closest_similarity) }}）</p>
          </div>
        </div>
        <h5>证据链</h5>
        <div class="evidence-grid">
          <article v-for="evidence in detail.evidence_chain" :key="evidence.type">
            <strong>{{ evidenceLabel(evidence.type) }}</strong><p>{{ evidence.description }}</p><small>置信度 {{ percent(evidence.confidence) }} · {{ evidence.supporting_ids.length }} 条引用</small>
          </article>
        </div>
      </template>
    </section>

    <section class="panel change-panel">
      <div class="panel-title"><div><h3>既有岗位能力动态更新</h3><p>比较 2.3 中两个同粒度周期快照，生成可审核的完整变更日志。</p></div></div>
      <form class="filters compact" @submit.prevent="analyzeChanges">
        <label><span>岗位 ID</span><input v-model.trim="changeQuery.job_id" required placeholder="job:backend-engineer" /></label>
        <label><span>起始周期</span><input v-model.trim="changeQuery.from_period" required placeholder="2025Q1" /></label>
        <label><span>目标周期</span><input v-model.trim="changeQuery.to_period" required placeholder="2025Q2" /></label>
        <label><span>变化阈值</span><input v-model.number="changeQuery.change_threshold" type="number" min="0" max="1" step="0.01" /></label>
        <button class="primary-button">生成变更日志</button>
      </form>
      <div v-if="changeWarnings.length" class="quality-warning">{{ changeWarnings.join('；') }}</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>能力项</th><th>类型</th><th>变化前</th><th>变化后</th><th>Delta</th><th>证据</th><th>审核</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="change in changes" :key="change.change_id">
              <td>{{ change.entity_name }}<small>{{ change.entity_id }}</small></td>
              <td>{{ changeTypeLabel(change.change_type) }}</td>
              <td>{{ ratioOf(change.before) }}</td><td>{{ ratioOf(change.after) }}</td><td>{{ signed(change.delta) }}</td>
              <td>{{ change.evidence_ids.length }}</td><td>{{ reviewLabel(change.review_status) }}</td>
              <td><button @click="reviewChange(change, 'approved')">通过</button><button class="danger" @click="reviewChange(change, 'rejected')">驳回</button></td>
            </tr>
            <tr v-if="!changes.length"><td colspan="8" class="empty">尚无变更日志。</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import jobsApi from '../api/jobs'

const reviewer = ref('人工审核员')
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
  try { stats.value = (await jobsApi.getDiscoverStats()).data } catch (_) { /* 尚未初始化时保持零值 */ }
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
  if (!confirm('确认定义无误并写入 2.3 知识图谱？')) return
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
function evidenceLabel(value) { return ({ community_cluster: '技能社区', skill_novelty: '组合 Novelty', jd_frequency_surge: 'JD 趋势异常', multi_source_support: '多源交叉验证' })[value] || value }
function errorMessage(error, prefix) { const detail = error.response?.data?.detail; return `${prefix}：${typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : error.message}` }
</script>

<style scoped>
.page { max-width: 1400px; }
.page-heading,.panel-title { display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin-bottom:18px }.page-heading h2,.panel-title h3{margin:0}.page-heading p,.panel-title p{margin:5px 0 0;color:#64748b}.eyebrow{font-size:11px;font-weight:800;letter-spacing:.14em;color:#2563eb;margin:0}.reviewer{display:flex;flex-direction:column;font-size:12px;color:#64748b}
.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:end;background:#fff;padding:16px;border-radius:12px;margin-bottom:18px;box-shadow:0 2px 8px #0000000f}.filters.compact{box-shadow:none;padding:0}.filters label,.edit-form label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:#64748b}.filters input,.reviewer input,.edit-form input,.edit-form textarea{border:1px solid #cbd5e1;border-radius:7px;padding:8px;font:inherit;background:#fff}.primary-button,button{border:1px solid #cbd5e1;background:#fff;border-radius:7px;padding:7px 11px;cursor:pointer}.primary-button{background:#2563eb;color:#fff;border-color:#2563eb}.danger{color:#b91c1c;border-color:#fecaca}button:disabled{opacity:.45;cursor:not-allowed}
.message,.quality-warning{padding:13px 16px;border-radius:10px;margin-bottom:16px}.error-message{background:#fef2f2;color:#b91c1c}.quality-warning{background:#fff7ed;color:#9a3412}.quality-warning ul{margin:6px 0 0}.summary-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:18px}.summary-grid article,.panel{background:#fff;border-radius:12px;box-shadow:0 2px 8px #0000000f;padding:18px}.summary-grid span{font-size:11px;color:#64748b}.summary-grid strong{display:block;font-size:25px}.green{color:#15803d}.red{color:#b91c1c}.panel{margin-bottom:18px}.batch-actions{display:flex;align-items:center;gap:8px;font-size:12px}
.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:9px;border-bottom:1px solid #e2e8f0;vertical-align:top}th{font-size:11px;color:#64748b}td small{display:block;color:#94a3b8;margin-top:3px}td a{color:#2563eb;font-weight:650;text-decoration:none}.empty{text-align:center;color:#94a3b8;padding:28px}.status,.tag{display:inline-block;border-radius:12px;padding:3px 9px;font-size:11px}.status.pending{background:#fef3c7}.status.adopted{background:#dcfce7;color:#166534}.status.rejected{background:#fee2e2;color:#991b1b}progress{width:70px;height:7px}
.definition-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}.definition-grid h4{font-size:20px;margin:0 0 8px}.definition-grid h5,.detail-panel>h5{margin:18px 0 7px}.definition-grid ul{padding-left:20px}.tag{margin:2px 5px 2px 0}.tag.required{background:#dbeafe;color:#1e40af}.tag.bonus{background:#f3e8ff;color:#6b21a8}.tag.industry{background:#dcfce7;color:#166534}.meta{margin-top:18px;color:#64748b;font-size:12px}.evidence-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.evidence-grid article{border:1px solid #e2e8f0;border-radius:9px;padding:12px}.evidence-grid p{margin:5px 0;color:#475569}.evidence-grid small{color:#94a3b8}.edit-form{display:grid;grid-template-columns:1fr 1fr;gap:12px}.edit-form label:nth-child(2),.edit-form label:nth-child(5),.edit-form label:nth-child(6),.edit-form div{grid-column:1/-1}.change-panel{margin-top:26px}
@media(max-width:900px){.summary-grid{grid-template-columns:repeat(2,1fr)}.definition-grid,.edit-form,.evidence-grid{grid-template-columns:1fr}.page-heading{align-items:flex-start;flex-direction:column}}
</style>
