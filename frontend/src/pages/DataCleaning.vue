<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h2 class="page-title">🧹 数据清洗</h2>
        <p class="page-subtitle">上传 JD 数据文件（Excel / CSV），执行「清洗 → 去重 → 标注 → 数据集划分」完整流水线。</p>
      </div>
    </header>

    <!-- 两种清洗方式：上传文件 / 从采集获取 -->
    <section class="upload-panel">
      <div class="mode-grid">
        <div class="mode-card">
          <div class="mode-title">方式一：上传文件</div>
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".xlsx,.csv"
            :file-list="fileList"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :on-exceed="onExceed"
          >
            <div class="upload-inner">
              <div class="upload-icon">📊</div>
              <div class="upload-text">拖拽 JD 数据文件到这里，或 <em>点击选择</em></div>
              <div class="upload-hint">.xlsx / .csv</div>
            </div>
          </el-upload>
          <div class="mode-actions">
            <el-button type="primary" :loading="running" :disabled="!fileList.length" @click="runCleaning">
              {{ running ? '正在清洗…' : '开始清洗' }}
            </el-button>
            <el-button :disabled="!fileList.length || running" @click="resetFiles">清空</el-button>
          </div>
        </div>

        <div class="mode-card">
          <div class="mode-title">方式二：从数据采集获取数据</div>
          <div class="collection-box">
            <div class="upload-icon">🔍</div>
            <div class="upload-text">直接使用「数据采集」页最近一次采集的数据进行清洗</div>
            <div class="upload-hint">无需手动上传文件</div>
          </div>
          <div class="mode-actions">
            <el-button type="success" :loading="runningCollection" @click="runFromCollection">
              {{ runningCollection ? '正在清洗…' : '从采集数据清洗' }}
            </el-button>
          </div>
        </div>
      </div>
      <el-alert v-if="error" class="message" type="error" :title="error" show-icon :closable="false" />
    </section>

    <!-- 结果 -->
    <template v-if="summary">
      <section class="summary-grid">
        <div class="summary-card">
          <div class="summary-label">原始数据</div>
          <div class="summary-value">{{ summary.data_flow?.original ?? '—' }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">清洗后</div>
          <div class="summary-value">{{ summary.data_flow?.after_cleaning ?? '—' }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">去重后</div>
          <div class="summary-value">{{ summary.data_flow?.after_deduplication ?? '—' }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">最终数据</div>
          <div class="summary-value">{{ summary.data_flow?.final ?? '—' }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">高质量</div>
          <div class="summary-value good">{{ summary.quality_metrics?.high_quality_count ?? '—' }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">待人工校验</div>
          <div class="summary-value warn">{{ summary.quality_metrics?.needs_review_count ?? '—' }}</div>
        </div>
      </section>

      <section v-if="summary.dataset_splits" class="split-row">
        <el-tag effect="plain">训练集 {{ summary.dataset_splits.train ?? 0 }}</el-tag>
        <el-tag type="success" effect="plain">验证集 {{ summary.dataset_splits.val ?? 0 }}</el-tag>
        <el-tag type="warning" effect="plain">测试集 {{ summary.dataset_splits.test ?? 0 }}</el-tag>
      </section>
    </template>

    <!-- 数据集列表 -->
    <section class="dataset-section">
      <div class="section-head">
        <h3>清洗后数据集</h3>
        <el-button size="small" :loading="loadingList" @click="loadDatasets">刷新</el-button>
      </div>
      <el-table :data="datasets" v-loading="loadingList" highlight-current-row class="dataset-table">
        <el-table-column label="岗位" min-width="160">
          <template #default="{ row }">{{ row.title }}</template>
        </el-table-column>
        <el-table-column label="来源" min-width="120">
          <template #default="{ row }">{{ row.source_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="质量分" width="130">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.quality_score ?? 0) * 100)"
              :stroke-width="6"
              :show-text="false"
              :color="row.quality_score >= 0.8 ? '#10b981' : row.quality_score >= 0.6 ? '#f59e0b' : '#ef4444'"
            />
            <span class="score-text">{{ Math.round((row.quality_score ?? 0) * 100) }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="180">
          <template #default="{ row }">
            <div v-if="row.tags && row.tags.length" class="tag-list">
              <el-tag v-for="t in row.tags.slice(0, 4)" :key="t" size="small" effect="plain">{{ t }}</el-tag>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="内容摘要" min-width="260">
          <template #default="{ row }">
            <span class="muted">{{ (row.content || '').slice(0, 60) }}{{ (row.content || '').length > 60 ? '…' : '' }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无清洗结果，请先上传文件运行清洗" :image-size="80" />
        </template>
      </el-table>
      <div class="pagination-row" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadDatasets"
          @size-change="loadDatasets"
        />
      </div>
    </section>

    <!-- 待人工校验 -->
    <section class="quality-section" v-if="qualityItems.length">
      <div class="section-head">
        <h3>待人工校验（{{ qualityItems.length }} 条）</h3>
      </div>
      <el-table :data="qualityItems" class="quality-table">
        <el-table-column prop="id" label="ID" width="140" />
        <el-table-column label="问题" min-width="180">
          <template #default="{ row }">
            <div v-if="row.issues && row.issues.length" class="tag-list">
              <el-tag v-for="i in row.issues" :key="i" size="small" type="warning" effect="plain">{{ i }}</el-tag>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="内容摘要" min-width="320">
          <template #default="{ row }">
            <span class="muted">{{ (row.original_text || '').slice(0, 80) }}…</span>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import cleaningApi from '../api/dataCleaning'

const fileList = ref([])
const running = ref(false)
const runningCollection = ref(false)
const error = ref('')

const summary = ref(null)
const datasets = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loadingList = ref(false)
const qualityItems = ref([])

const ACCEPT_TYPES = ['xlsx', 'csv']

function onFileChange(_uploadFile, uploadFiles) {
  fileList.value = uploadFiles
}
function onFileRemove(_uploadFile, uploadFiles) {
  fileList.value = uploadFiles
}
function onExceed() {
  ElMessage.warning('一次只能上传一个数据文件')
}
function resetFiles() {
  fileList.value = []
  summary.value = null
  datasets.value = []
  total.value = 0
  qualityItems.value = []
}

async function runCleaning() {
  const raw = fileList.value[0]?.raw
  if (!raw) return
  const suffix = (raw.name.split('.').pop() || '').toLowerCase()
  if (!ACCEPT_TYPES.includes(suffix)) {
    ElMessage.error('仅支持 .xlsx / .csv 文件')
    return
  }
  running.value = true
  error.value = ''
  try {
    const formData = new FormData()
    formData.append('file', raw)
    const task = await cleaningApi.createTask(formData)
    summary.value = task.summary || null
    ElMessage.success('清洗完成')
    await Promise.all([loadDatasets(), loadQualityItems()])
  } catch (err) {
    error.value = err.response?.data?.detail || '清洗失败，请重试'
  } finally {
    running.value = false
  }
}

async function runFromCollection() {
  runningCollection.value = true
  error.value = ''
  try {
    const task = await cleaningApi.createTaskFromCollection()
    summary.value = task.summary || null
    ElMessage.success('已从采集数据完成清洗')
    await Promise.all([loadDatasets(), loadQualityItems()])
  } catch (err) {
    error.value = err.response?.data?.detail || '从采集数据清洗失败'
  } finally {
    runningCollection.value = false
  }
}

async function loadDatasets() {
  loadingList.value = true
  try {
    const data = await cleaningApi.listDatasets({ page: page.value, page_size: pageSize.value })
    datasets.value = data.items || []
    total.value = data.total || 0
  } catch {
    datasets.value = []
    total.value = 0
  } finally {
    loadingList.value = false
  }
}

async function loadQualityItems() {
  try {
    const data = await cleaningApi.listQualityItems()
    qualityItems.value = data.items || []
  } catch {
    qualityItems.value = []
  }
}

onMounted(() => {
  loadDatasets()
  loadQualityItems()
})
</script>

<style scoped>
.page { animation: fadeIn .3s ease; }
.page-title { margin: 0; font-size: 22px; color: #0f172a; }
.page-subtitle { margin: 8px 0 0; color: #64748b; font-size: 14px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

.page-header { margin-bottom: 20px; }
.upload-panel { margin-bottom: 22px; }
.upload-inner { padding: 16px 0; text-align: center; }
.upload-icon { font-size: 40px; }
.upload-text { margin-top: 8px; color: #0f172a; font-size: 15px; }
.upload-text em { color: #2563eb; font-style: normal; font-weight: 650; }
.upload-hint { margin-top: 6px; color: #94a3b8; font-size: 12px; }
.mode-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.mode-card { padding: 16px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; }
.mode-title { margin-bottom: 12px; color: #0f172a; font-weight: 700; font-size: 15px; }
.mode-actions { display: flex; gap: 10px; margin-top: 14px; }
.collection-box { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 150px; padding: 16px; border: 2px dashed #cbd5e1; border-radius: 12px; background: #f8fafc; text-align: center; }
.message { margin-top: 14px; }
@media (max-width: 800px) { .mode-grid { grid-template-columns: 1fr; } }

.summary-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 14px; }
.summary-card { padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; }
.summary-label { color: #64748b; font-size: 12px; }
.summary-value { margin-top: 6px; color: #0f172a; font-size: 24px; font-weight: 700; }
.summary-value.good { color: #10b981; }
.summary-value.warn { color: #f59e0b; }
.split-row { display: flex; gap: 8px; margin-bottom: 22px; }

.dataset-section, .quality-section { margin-top: 22px; }
.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-head h3 { margin: 0; color: #0f172a; font-size: 16px; }
.dataset-table, .quality-table { border: 1px solid #e2e8f0; border-radius: 12px; }
.score-text { margin-left: 6px; color: #475569; font-size: 12px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 4px; }
.muted { color: #94a3b8; }
.pagination-row { margin-top: 14px; display: flex; justify-content: flex-end; }
@media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(3, 1fr); } }
</style>
