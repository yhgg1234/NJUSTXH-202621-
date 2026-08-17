<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h2 class="page-title">📄 简历解析</h2>
        <p class="page-subtitle">支持 PDF / DOCX 简历上传，通过大模型抽取基本信息、教育/工作/项目经历、技能/证书/语言能力等结构化字段。</p>
      </div>
    </header>

    <!-- 上传面板 -->
    <section class="upload-panel">
      <el-upload
        drag
        multiple
        :auto-upload="false"
        accept=".pdf,.docx"
        :limit="20"
        :file-list="fileList"
        :on-change="onFileChange"
        :on-remove="onFileRemove"
        :on-exceed="onExceed"
      >
        <div class="upload-inner">
          <div class="upload-icon">📤</div>
          <div class="upload-text">将简历文件拖拽到此处，或 <em>点击选择文件</em></div>
          <div class="upload-hint">仅支持 PDF / DOCX 格式，单文件 ≤ 10MB，最多选择 20 个；解析含大模型抽取，单份约需 1~3 分钟，请耐心等待</div>
        </div>
      </el-upload>
      <div class="upload-actions">
        <el-button type="primary" :loading="uploading" :disabled="!fileList.length" @click="handleUpload">
          {{ uploading ? '正在解析，请稍候（约 1~3 分钟）...' : '开始解析' }}
        </el-button>
        <el-button :disabled="!fileList.length || uploading" @click="resetFiles">清空文件</el-button>
        <el-tag v-if="uploadedCount" type="success" effect="plain" class="upload-ok">
          ✔ 已成功解析 {{ uploadedCount }} 份简历
        </el-tag>
      </div>
    </section>

    <el-alert v-if="error" class="message" type="error" :title="error" show-icon :closable="false" />

    <!-- 列表 + 详情 -->
    <div class="content-layout">
      <section class="list-panel">
        <div class="section-head">
          <h3>简历列表</h3>
          <el-input
            v-model="keyword"
            placeholder="搜索姓名 / 邮箱 / 技能 / 文件名"
            clearable
            class="search-input"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #append>
              <el-button @click="handleSearch">搜索</el-button>
            </template>
          </el-input>
        </div>
        <el-table
          :data="resumes"
          v-loading="listLoading"
          highlight-current-row
          class="resume-table"
          @row-click="onRowClick"
        >
          <el-table-column label="文件" min-width="200">
            <template #default="{ row }">
              <div class="file-cell">
                <span class="file-icon">📄</span>
                <div class="file-meta">
                  <div class="file-name">{{ row.file_name }}</div>
                  <div class="file-id">{{ row.id }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="姓名" width="100">
            <template #default="{ row }">
              <span :class="{ muted: !row.name }">{{ row.name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="联系方式" min-width="170">
            <template #default="{ row }">
              <div class="contact" :class="{ muted: !row.email }">{{ row.email || '—' }}</div>
              <div class="contact" :class="{ muted: !row.phone }">{{ row.phone || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="技能" min-width="150">
            <template #default="{ row }">
              <div v-if="row.skills && row.skills.length" class="tag-list">
                <el-tag v-for="s in row.skills.slice(0, 3)" :key="s" size="small" effect="plain">{{ s }}</el-tag>
                <el-tag v-if="row.skills.length > 3" size="small" type="info">+{{ row.skills.length - 3 }}</el-tag>
              </div>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="120">
            <template #default="{ row }">
              <el-progress :percentage="Math.round((row.confidence || 0) * 100)" :stroke-width="6" :show-text="false" />
              <span class="conf-text">{{ Math.round((row.confidence || 0) * 100) }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="解析时间" width="165">
            <template #default="{ row }">{{ formatTime(row.parsed_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="loadDetail(row)">详情</el-button>
              <el-button text type="danger" size="small" @click.stop="confirmDelete(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无简历，请先上传文件" :image-size="80" />
          </template>
        </el-table>
        <div class="pagination-row">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadResumes"
            @size-change="loadResumes"
          />
        </div>
      </section>

      <!-- 详情面板 -->
      <section class="detail-panel" v-loading="detailLoading">
        <template v-if="selected">
          <div class="detail-head">
            <div class="avatar">{{ (selected.name || '?').slice(0, 1) }}</div>
            <div class="detail-basic">
              <h3 class="detail-name">{{ selected.name || '未识别姓名' }}</h3>
              <div class="detail-contact">
                <span v-if="selected.email">{{ selected.email }}</span>
                <span v-if="selected.phone">{{ selected.phone }}</span>
                <span v-if="!selected.email && !selected.phone" class="muted">未提取到联系方式</span>
              </div>
              <div class="detail-file">📄 {{ selected.file_name }}</div>
            </div>
          </div>
          <el-descriptions :column="2" border size="small" class="detail-desc">
            <el-descriptions-item label="解析时间">{{ formatTime(selected.parsed_at) }}</el-descriptions-item>
            <el-descriptions-item label="置信度">
              <el-progress :percentage="Math.round((selected.confidence || 0) * 100)" :stroke-width="8" :color="confColor" />
            </el-descriptions-item>
          </el-descriptions>

          <div class="detail-section">
            <div class="detail-section-title">🧰 技能</div>
            <div v-if="selected.skills && selected.skills.length" class="tag-list">
              <el-tag v-for="s in selected.skills" :key="s" effect="light" type="primary">{{ s }}</el-tag>
            </div>
            <div v-else class="muted">—</div>
          </div>

          <div class="detail-section">
            <div class="detail-section-title">🎓 教育经历</div>
            <div v-if="selected.education && selected.education.length">
              <div v-for="(edu, i) in selected.education" :key="i" class="exp-item">
                <div class="exp-head">
                  <strong>{{ edu.school }}</strong>
                  <span class="exp-tag">{{ edu.degree }}</span>
                  <span class="exp-time">{{ dateRange(edu.start_date, edu.end_date) }}</span>
                </div>
                <div v-if="edu.major" class="exp-detail">专业：{{ edu.major }}</div>
              </div>
            </div>
            <div v-else class="muted">—</div>
          </div>

          <div class="detail-section">
            <div class="detail-section-title">💼 工作经历</div>
            <div v-if="selected.work_experience && selected.work_experience.length">
              <div v-for="(w, i) in selected.work_experience" :key="i" class="exp-item">
                <div class="exp-head">
                  <strong>{{ w.company }}</strong>
                  <span class="exp-tag">{{ w.position }}</span>
                  <span class="exp-time">{{ dateRange(w.start_date, w.end_date) }}</span>
                </div>
                <p v-if="w.description" class="exp-desc">{{ w.description }}</p>
                <ul v-if="w.achievements && w.achievements.length" class="exp-list">
                  <li v-for="(a, j) in w.achievements" :key="j">{{ a }}</li>
                </ul>
              </div>
            </div>
            <div v-else class="muted">—</div>
          </div>

          <div class="detail-section">
            <div class="detail-section-title">🚀 项目经验</div>
            <div v-if="selected.projects && selected.projects.length">
              <div v-for="(p, i) in selected.projects" :key="i" class="exp-item">
                <div class="exp-head">
                  <strong>{{ p.name }}</strong>
                  <span class="exp-tag">{{ p.role }}</span>
                  <span class="exp-time">{{ dateRange(p.start_date, p.end_date) }}</span>
                </div>
                <p v-if="p.description" class="exp-desc">{{ p.description }}</p>
                <div v-if="p.tech_stacks && p.tech_stacks.length" class="tag-list">
                  <el-tag v-for="t in p.tech_stacks" :key="t" size="small" effect="plain" type="info">{{ t }}</el-tag>
                </div>
                <ul v-if="p.achievements && p.achievements.length" class="exp-list">
                  <li v-for="(a, j) in p.achievements" :key="j">{{ a }}</li>
                </ul>
              </div>
            </div>
            <div v-else class="muted">—</div>
          </div>

          <div class="detail-section">
            <div class="detail-section-title">🏅 证书 / 语言</div>
            <div v-if="(selected.certificates && selected.certificates.length) || (selected.languages && selected.languages.length)" class="tag-list">
              <el-tag v-for="c in selected.certificates || []" :key="c" type="success" effect="plain">{{ c }}</el-tag>
              <el-tag v-for="l in selected.languages || []" :key="l" type="warning" effect="plain">{{ l }}</el-tag>
            </div>
            <div v-else class="muted">—</div>
          </div>
        </template>
        <el-empty v-else description="点击左侧列表中的简历查看结构化解析结果" :image-size="90" />
      </section>
    </div>

    <!-- 删除确认 -->
    <el-dialog v-model="deleteVisible" title="删除简历" width="420px">
      <p class="delete-tip">确定要删除「{{ deletingRow?.file_name || '' }}」吗？删除后该记录不可恢复。</p>
      <template #footer>
        <el-button @click="deleteVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleteLoading" @click="doDelete">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import resumeApi from '../api/resume'

// ── 上传状态 ──
const fileList = ref([])
const uploading = ref(false)
const uploadedCount = ref(0)
const error = ref('')

// ── 列表状态 ──
const resumes = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const listLoading = ref(false)
const keyword = ref('')

// ── 详情状态 ──
const selected = ref(null)
const detailLoading = ref(false)

// ── 删除状态 ──
const deleteVisible = ref(false)
const deletingRow = ref(null)
const deleteLoading = ref(false)

const MAX_FILE_SIZE = 10 * 1024 * 1024
const MAX_FILES = 20
const ACCEPT_TYPES = ['pdf', 'docx']

// ── 上传 ──
function onFileChange(_uploadFile, uploadFiles) {
  fileList.value = uploadFiles
}

function onFileRemove(_uploadFile, uploadFiles) {
  fileList.value = uploadFiles
}

function onExceed() {
  ElMessage.warning(`最多支持同时选择 ${MAX_FILES} 个文件`)
}

function resetFiles() {
  fileList.value = []
}

async function handleUpload() {
  const raws = fileList.value.map((f) => f.raw).filter(Boolean)
  if (!raws.length) return

  const invalid = raws.filter((f) => {
    const suffix = (f.name.split('.').pop() || '').toLowerCase()
    return !ACCEPT_TYPES.includes(suffix) || f.size > MAX_FILE_SIZE
  })
  if (invalid.length) {
    ElMessage.error('存在不支持的文件：仅支持 PDF / DOCX 且单文件 ≤ 10MB')
    return
  }

  uploading.value = true
  error.value = ''
  try {
    const formData = new FormData()
    if (raws.length === 1) {
      formData.append('file', raws[0])
      const result = await resumeApi.upload(formData)
      uploadedCount.value = 1
      selected.value = result
      ElMessage.success(`解析成功：${result.file_name}`)
    } else {
      raws.forEach((f) => formData.append('files', f))
      const { results = [] } = await resumeApi.batchUpload(formData)
      const ok = results.filter((r) => r.id)
      uploadedCount.value = ok.length
      if (ok.length) selected.value = ok[0]
      ElMessage.success(`批量解析完成：成功 ${ok.length} / ${results.length} 份`)
    }
    fileList.value = []
    await loadResumes()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '上传解析失败'
  } finally {
    uploading.value = false
  }
}

// ── 列表 ──
async function loadResumes() {
  listLoading.value = true
  error.value = ''
  try {
    const data = await resumeApi.listResumes({ page: page.value, page_size: pageSize.value })
    resumes.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载简历列表失败'
  } finally {
    listLoading.value = false
  }
}

async function handleSearch() {
  page.value = 1
  const kw = keyword.value.trim()
  if (!kw) {
    return loadResumes()
  }
  listLoading.value = true
  error.value = ''
  try {
    const data = await resumeApi.searchResumes({ keyword: kw, page: page.value, page_size: pageSize.value })
    resumes.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.warning('检索接口暂不可用，已加载完整列表')
    await loadResumes()
  } finally {
    listLoading.value = false
  }
}

// ── 详情 ──
async function loadDetail(row) {
  detailLoading.value = true
  error.value = ''
  try {
    selected.value = await resumeApi.getResume(row.id)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '获取简历详情失败'
  } finally {
    detailLoading.value = false
  }
}

function onRowClick(row) {
  loadDetail(row)
}

// ── 删除 ──
function confirmDelete(row) {
  deletingRow.value = row
  deleteVisible.value = true
}

async function doDelete() {
  deleteLoading.value = true
  error.value = ''
  try {
    await resumeApi.deleteResume(deletingRow.value.id)
    ElMessage.success('删除成功')
    deleteVisible.value = false
    if (selected.value && selected.value.id === deletingRow.value.id) {
      selected.value = null
    }
    await loadResumes()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '删除失败'
  } finally {
    deleteLoading.value = false
  }
}

// ── 工具函数 ──
function formatTime(t) {
  if (!t) return '—'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function dateRange(start, end) {
  if (!start && !end) return ''
  return `${start || '?'} ~ ${end || '至今'}`
}

function confColor(percentage) {
  if (percentage >= 80) return '#16a34a'
  if (percentage >= 50) return '#d97706'
  return '#dc2626'
}

onMounted(loadResumes)
</script>

<style scoped>
.page { animation: fadeIn .3s ease; }
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.page-title { margin: 0; font-size: 22px; color: #0f172a; }
.page-subtitle { margin: 6px 0 0; color: #64748b; font-size: 13px; }

/* 上传面板 */
.upload-panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px 18px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, .04);
}
.upload-inner { padding: 10px 0; }
.upload-icon { font-size: 40px; margin-bottom: 8px; }
.upload-text { font-size: 15px; color: #334155; }
.upload-text em { color: #2563eb; font-style: normal; }
.upload-hint { font-size: 12px; color: #94a3b8; margin-top: 6px; }
.upload-actions { display: flex; align-items: center; gap: 10px; margin-top: 6px; }
.upload-ok { margin-left: 4px; }

.message { margin-bottom: 16px; }

/* 布局 */
.content-layout {
  display: grid;
  grid-template-columns: minmax(560px, 1.6fr) minmax(340px, 1fr);
  gap: 16px;
  align-items: start;
}
.list-panel,
.detail-panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, .04);
}
.list-panel { padding: 16px 18px; }
.detail-panel { padding: 18px; min-height: 420px; }

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.section-head h3 { margin: 0; font-size: 17px; }
.search-input { width: 280px; }

.resume-table { width: 100%; }
.file-cell { display: flex; align-items: center; gap: 10px; }
.file-icon { font-size: 22px; }
.file-meta { min-width: 0; }
.file-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-id {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.contact { font-size: 12px; color: #334155; line-height: 1.5; }
.conf-text { font-size: 11px; color: #64748b; }
.muted { color: #94a3b8; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }

.pagination-row { display: flex; justify-content: flex-end; margin-top: 14px; }

/* 详情面板 */
.detail-head { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
.avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #2563eb;
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 22px;
  font-weight: 700;
  flex-shrink: 0;
}
.detail-basic { min-width: 0; }
.detail-name { margin: 0; font-size: 19px; color: #0f172a; }
.detail-contact {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #475569;
  margin-top: 4px;
}
.detail-file { font-size: 12px; color: #94a3b8; margin-top: 4px; }
.detail-desc { margin-bottom: 6px; }

.detail-section { margin-top: 18px; }
.detail-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  padding-bottom: 8px;
  margin-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}
.exp-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 10px;
}
.exp-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.exp-head strong { font-size: 14px; color: #0f172a; }
.exp-tag {
  font-size: 12px;
  color: #2563eb;
  background: #eff6ff;
  border-radius: 4px;
  padding: 1px 8px;
}
.exp-time { font-size: 12px; color: #94a3b8; margin-left: auto; }
.exp-detail { font-size: 13px; color: #475569; margin-top: 6px; }
.exp-desc { font-size: 13px; color: #475569; line-height: 1.7; margin: 8px 0 0; }
.exp-list { margin: 8px 0 0; padding-left: 18px; color: #334155; font-size: 13px; line-height: 1.7; }

.delete-tip { margin: 0; color: #334155; font-size: 14px; line-height: 1.7; }

@media (max-width: 1080px) {
  .content-layout { grid-template-columns: 1fr; }
  .search-input { width: 100%; }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>

