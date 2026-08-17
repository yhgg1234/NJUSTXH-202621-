<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h2 class="page-title">🔍 数据采集</h2>
        <p class="page-subtitle">选择数据源，创建采集任务，浏览采集到的原始 JD 数据（含 PII 过滤与去重）。</p>
      </div>
    </header>

    <!-- 数据源 -->
    <section class="section">
      <div class="section-head"><h3>数据源</h3></div>
      <div class="source-grid">
        <div v-for="s in sources" :key="s.id" class="source-card" :class="{ active: form.source_id === s.id }" @click="form.source_id = s.id">
          <div class="source-name">{{ s.name }}</div>
          <div class="source-desc">{{ s.description }}</div>
          <el-tag size="small" :type="s.id === 'public_search_demo' ? 'success' : 'warning'" effect="plain">
            {{ s.id === 'public_search_demo' ? '演示·不联网' : '需配置 Cookie' }}
          </el-tag>
        </div>
      </div>
    </section>

    <!-- 采集表单 -->
    <section class="section">
      <div class="section-head"><h3>创建采集任务</h3></div>
      <div class="task-form">
        <div class="form-field">
          <span>关键词（逗号分隔）</span>
          <el-input v-model="form.keywords" placeholder="例如：数据分析师, AI工程师" />
        </div>
        <div class="form-field">
          <span>最大翻页数</span>
          <el-input-number v-model="form.max_pages" :min="1" :max="100" />
        </div>
        <el-button type="primary" :loading="running" :disabled="!form.source_id || !form.keywords" @click="runTask">
          {{ running ? '采集中…' : '开始采集' }}
        </el-button>
      </div>
      <el-alert v-if="error" class="message" type="error" :title="error" show-icon :closable="false" />
    </section>

    <!-- 任务结果 -->
    <section v-if="lastTask" class="section">
      <div class="section-head"><h3>最近任务结果</h3></div>
      <div class="summary-grid">
        <div class="summary-card"><div class="summary-label">采集到</div><div class="summary-value good">{{ lastTask.collected_count ?? '—' }}</div></div>
        <div class="summary-card"><div class="summary-label">丢弃 PII</div><div class="summary-value">{{ lastTask.dropped_pii ?? '—' }}</div></div>
        <div class="summary-card"><div class="summary-label">去重</div><div class="summary-value">{{ lastTask.dropped_dup ?? '—' }}</div></div>
        <div class="summary-card"><div class="summary-label">唯一岗位</div><div class="summary-value">{{ lastTask.report?.unique_job_titles ?? '—' }}</div></div>
      </div>
    </section>

    <!-- 原始数据 -->
    <section class="section">
      <div class="section-head">
        <h3>原始数据</h3>
        <el-button size="small" :loading="loading" @click="loadRawData">刷新</el-button>
      </div>
      <el-table :data="rawData" v-loading="loading" class="data-table">
        <el-table-column label="岗位" min-width="160">
          <template #default="{ row }">{{ row.title }}</template>
        </el-table-column>
        <el-table-column label="来源" width="110">
          <template #default="{ row }">{{ row.source_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="公司 / 城市" min-width="150">
          <template #default="{ row }">
            <span>{{ row.raw_metadata?.company || '—' }}</span>
            <span class="muted" v-if="row.raw_metadata?.city"> · {{ row.raw_metadata.city }}</span>
          </template>
        </el-table-column>
        <el-table-column label="技能" min-width="160">
          <template #default="{ row }">
            <div v-if="row.raw_metadata?.raw_skills" class="tag-list">
              <el-tag v-for="t in (row.raw_metadata.raw_skills || '').split(',').slice(0, 4)" :key="t" size="small" effect="plain">{{ t.trim() }}</el-tag>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="链接" min-width="180">
          <template #default="{ row }">
            <a v-if="row.url" :href="row.url" target="_blank" class="link">{{ row.url }}</a>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无采集数据，请先创建采集任务" :image-size="80" />
        </template>
      </el-table>
      <div class="pagination-row" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadRawData"
          @size-change="loadRawData"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import collectionApi from '../api/dataCollection'

const sources = ref([])
const form = reactive({ source_id: 'public_search_demo', keywords: '数据分析师', max_pages: 3 })
const running = ref(false)
const error = ref('')

const rawData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const lastTask = ref(null)

async function loadSources() {
  try {
    const data = await collectionApi.listSources()
    sources.value = data.items || []
  } catch {
    sources.value = []
  }
}

async function runTask() {
  const keywords = form.keywords.split(/[,，、]/).map((s) => s.trim()).filter(Boolean)
  if (!keywords.length) {
    ElMessage.warning('请输入关键词')
    return
  }
  running.value = true
  error.value = ''
  try {
    const task = await collectionApi.createTask({
      source_ids: [form.source_id],
      keywords,
      max_pages: form.max_pages,
    })
    lastTask.value = task
    ElMessage.success(`采集完成，共 ${task.collected_count ?? 0} 条`)
    await loadRawData()
  } catch (err) {
    error.value = err.response?.data?.detail || '采集失败，请重试'
  } finally {
    running.value = false
  }
}

async function loadRawData() {
  loading.value = true
  try {
    const data = await collectionApi.listRawData({ page: page.value, page_size: pageSize.value })
    rawData.value = data.items || []
    total.value = data.total || 0
  } catch {
    rawData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadSources()
  loadRawData()
})
</script>

<style scoped>
.page { animation: fadeIn .3s ease; }
.page-title { margin: 0; font-size: 22px; color: #0f172a; }
.page-subtitle { margin: 8px 0 0; color: #64748b; font-size: 14px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.page-header { margin-bottom: 20px; }

.section { margin-bottom: 24px; }
.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-head h3 { margin: 0; color: #0f172a; font-size: 16px; }

.source-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.source-card { padding: 14px; border: 2px solid #e2e8f0; border-radius: 12px; cursor: pointer; transition: border-color .2s, background .2s; }
.source-card:hover { border-color: #93c5fd; }
.source-card.active { border-color: #2563eb; background: #eff6ff; }
.source-name { color: #0f172a; font-weight: 650; }
.source-desc { margin: 6px 0 8px; color: #64748b; font-size: 13px; }

.task-form { display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap; }
.form-field { display: flex; flex-direction: column; gap: 6px; min-width: 240px; }
.form-field > span { color: #475569; font-size: 12px; font-weight: 700; }
.message { margin-top: 14px; }

.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.summary-card { padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; }
.summary-label { color: #64748b; font-size: 12px; }
.summary-value { margin-top: 6px; color: #0f172a; font-size: 22px; font-weight: 700; }
.summary-value.good { color: #10b981; }

.data-table { border: 1px solid #e2e8f0; border-radius: 12px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 4px; }
.muted { color: #94a3b8; }
.link { color: #2563eb; text-decoration: none; font-size: 12px; }
.link:hover { text-decoration: underline; }
.pagination-row { margin-top: 14px; display: flex; justify-content: flex-end; }
@media (max-width: 800px) { .source-grid { grid-template-columns: 1fr; } .summary-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
