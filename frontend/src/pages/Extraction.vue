<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h2 class="page-title">🧠 信息抽取</h2>
        <p class="page-subtitle">输入一段岗位 JD，由大模型 + RAG 抽取实体（岗位/技能/技术栈等）与关系，输出图谱 JSON。</p>
      </div>
      <div class="header-actions">
        <el-button size="small" type="success" :loading="batchLoading" @click="runFromCleaning">从数据清洗获取数据</el-button>
        <el-button size="small" :loading="ragLoading" @click="initRag">初始化 RAG 词库</el-button>
      </div>
    </header>

    <!-- 输入表单 -->
    <section class="input-panel">
      <div class="form-field">
        <span>岗位名称</span>
        <el-input v-model="form.job_title" placeholder="例如：AI Agent 开发工程师" />
      </div>
      <div class="form-field">
        <span>工作职责</span>
        <el-input v-model="form.responsibilities" type="textarea" :rows="4" placeholder="负责基于大模型的 Agent 应用开发…" />
      </div>
      <div class="form-field">
        <span>任职要求</span>
        <el-input v-model="form.requirements" type="textarea" :rows="4" placeholder="精通 Python、LangChain、RAG…" />
      </div>
      <div class="actions">
        <el-button type="primary" :loading="loading" @click="runExtract">
          {{ loading ? '抽取中（首次可能下载模型，约 1-3 分钟）…' : '开始抽取' }}
        </el-button>
      </div>
      <el-alert v-if="error" class="message" type="error" :title="error" show-icon :closable="false" />
    </section>

    <!-- 结果 -->
    <template v-if="result">
      <!-- 概览 -->
      <section class="overview">
        <div class="ov-card">
          <div class="ov-label">整体置信度</div>
          <div class="ov-value">{{ Math.round((result.overall_confidence ?? 0) * 100) }}%</div>
        </div>
        <div class="ov-card">
          <div class="ov-label">人工复核</div>
          <div class="ov-value" :class="result.needs_human_review ? 'warn' : 'good'">{{ result.needs_human_review ? '需要' : '不需要' }}</div>
        </div>
        <div class="ov-card">
          <div class="ov-label">实体数</div>
          <div class="ov-value">{{ result.entities?.length ?? 0 }}</div>
        </div>
        <div class="ov-card">
          <div class="ov-label">关系数</div>
          <div class="ov-value">{{ result.relations?.length ?? 0 }}</div>
        </div>
      </section>

      <el-alert v-if="result.quality_issues?.length" class="message" type="warning" :closable="false" show-icon>
        <template #title>
          质量问题：{{ result.quality_issues.join('；') }}
        </template>
      </el-alert>

      <!-- 快捷字段 -->
      <section v-if="derivedTags.length" class="section">
        <div class="section-title">快捷汇总</div>
        <div class="tag-groups">
          <div v-for="g in derivedTags" :key="g.label" class="tag-group">
            <span class="tag-group-label">{{ g.label }}</span>
            <div class="tag-list">
              <el-tag v-for="t in g.tags" :key="t" size="small" effect="plain">{{ t }}</el-tag>
            </div>
          </div>
        </div>
      </section>

      <!-- 实体 -->
      <section class="section">
        <div class="section-title">实体（{{ result.entities?.length ?? 0 }}）</div>
        <div v-if="result.entities?.length" class="entity-list">
          <div v-for="e in result.entities" :key="e.mention_id" class="entity-item">
            <el-tag size="small" :type="entityColor[e.type] || 'info'">{{ entityNames[e.type] || e.type }}</el-tag>
            <span class="entity-name">{{ e.name }}</span>
          </div>
        </div>
        <div v-else class="muted">—</div>
      </section>

      <!-- 关系 -->
      <section class="section">
        <div class="section-title">关系（{{ result.relations?.length ?? 0 }}）</div>
        <div v-if="result.relations?.length" class="relation-list">
          <div v-for="r in result.relations" :key="r.relation_id" class="relation-item">
            <span class="rel-node">{{ entityMap[r.head_mention_id] || r.head_mention_id }}</span>
            <el-tag size="small" type="success" effect="plain">{{ relationNames[r.type] || r.type }}</el-tag>
            <span class="rel-node">{{ entityMap[r.tail_mention_id] || r.tail_mention_id }}</span>
          </div>
        </div>
        <div v-else class="muted">—</div>
      </section>
    </template>

    <el-empty v-else description="输入 JD 内容后点击「开始抽取」" :image-size="100" />

    <!-- 批量抽取结果 -->
    <section v-if="batchResults.length" class="section batch-section">
      <div class="section-title">数据清洗结果批量抽取（{{ batchResults.length }} 条）</div>
      <el-table :data="batchResults" class="batch-table">
        <el-table-column label="岗位" min-width="150">
          <template #default="{ row }">{{ row.job_title }}</template>
        </el-table-column>
        <el-table-column label="实体" width="90">
          <template #default="{ row }">{{ row.entities?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="关系" width="90">
          <template #default="{ row }">{{ row.relations?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="置信度" width="100">
          <template #default="{ row }">{{ Math.round((row.overall_confidence ?? 0) * 100) }}%</template>
        </el-table-column>
        <el-table-column label="抽取到的实体" min-width="260">
          <template #default="{ row }">
            <div v-if="row.entities?.length" class="tag-list">
              <el-tag v-for="e in row.entities.slice(0, 6)" :key="e.mention_id" size="small" effect="plain">{{ e.name }}</el-tag>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无批量抽取结果" :image-size="80" />
        </template>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import extractionApi from '../api/extraction'

const form = reactive({ job_title: '', responsibilities: '', requirements: '' })
const loading = ref(false)
const ragLoading = ref(false)
const error = ref('')
const result = ref(null)
const batchLoading = ref(false)
const batchResults = ref([])

const entityNames = {
  position: '岗位', skill: '技能', tech_stack: '技术栈', certificate: '证书',
  industry: '行业', education: '学历', company: '公司', project: '项目',
}
const entityColor = {
  position: 'danger', skill: 'success', tech_stack: 'warning', certificate: 'info',
  industry: 'warning', education: 'info', company: 'primary', project: 'primary',
}
const relationNames = {
  requires: '要求', prefers: '偏好', prerequisite: '前置', same_as: '同义',
  related_to: '相关', belongs_to: '属于', evolved_from: '演化自', applies_to: '适用于',
}

const entityMap = computed(() => {
  const m = {}
  for (const e of result.value?.entities || []) {
    m[e.mention_id] = e.name
  }
  return m
})

const derivedTags = computed(() => {
  const d = result.value?.derived_fields || {}
  const groups = []
  const push = (label, value) => {
    const tags = (value || '').split(/[;；,，、]/).map((s) => s.trim()).filter(Boolean)
    if (tags.length) groups.push({ label, tags })
  }
  push('技能', d.raw_skills)
  push('技术栈', d.tech_stack)
  push('学历', d.education)
  push('证书', d.certificates)
  return groups
})

async function runExtract() {
  if (!form.job_title && !form.responsibilities && !form.requirements) {
    ElMessage.warning('请至少填写岗位名称或职责/要求')
    return
  }
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const resp = await extractionApi.extract({ ...form })
    result.value = resp.data || null
    ElMessage.success('抽取完成')
  } catch (err) {
    error.value = err.response?.data?.detail || '抽取失败，请重试'
  } finally {
    loading.value = false
  }
}

async function initRag() {
  ragLoading.value = true
  try {
    await extractionApi.initRag()
    ElMessage.success('RAG 词库初始化成功')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '初始化失败')
  } finally {
    ragLoading.value = false
  }
}

async function runFromCleaning() {
  batchLoading.value = true
  try {
    const resp = await extractionApi.fromCleaning(20)
    batchResults.value = resp.results || []
    ElMessage.success(resp.message || '批量抽取完成')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '从数据清洗获取数据失败')
  } finally {
    batchLoading.value = false
  }
}
</script>

<style scoped>
.page { animation: fadeIn .3s ease; }
.page-title { margin: 0; font-size: 22px; color: #0f172a; }
.page-subtitle { margin: 8px 0 0; color: #64748b; font-size: 14px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.batch-section { max-width: 900px; }
.batch-table { border: 1px solid #e2e8f0; border-radius: 12px; }

.input-panel { max-width: 760px; }
.form-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
.form-field > span { color: #475569; font-size: 13px; font-weight: 700; }
.actions { margin-top: 6px; }
.message { margin-top: 14px; }

.overview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px; }
.ov-card { padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; }
.ov-label { color: #64748b; font-size: 12px; }
.ov-value { margin-top: 6px; color: #0f172a; font-size: 22px; font-weight: 700; }
.ov-value.good { color: #10b981; }
.ov-value.warn { color: #f59e0b; }

.section { margin-top: 20px; max-width: 760px; }
.section-title { margin-bottom: 10px; color: #0f172a; font-weight: 700; font-size: 15px; }
.tag-groups { display: flex; flex-direction: column; gap: 10px; }
.tag-group { display: flex; align-items: center; gap: 10px; }
.tag-group-label { color: #64748b; font-size: 12px; font-weight: 700; min-width: 40px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }

.entity-list { display: flex; flex-wrap: wrap; gap: 8px; }
.entity-item { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 8px; }
.entity-name { color: #0f172a; font-weight: 600; }

.relation-list { display: flex; flex-direction: column; gap: 8px; }
.relation-item { display: flex; align-items: center; gap: 8px; }
.rel-node { color: #0f172a; font-weight: 600; }
.muted { color: #94a3b8; }
@media (max-width: 700px) { .overview { grid-template-columns: repeat(2, 1fr); } }
</style>
