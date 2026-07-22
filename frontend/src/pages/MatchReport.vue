<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h2 class="page-title">人岗匹配诊断</h2>
        <p class="page-subtitle">基于岗位能力要求、结构化简历和 Spark Lite 生成差距建议与学习路径。</p>
      </div>
      <el-tag :type="report?.llm_generated ? 'success' : 'info'" effect="plain">
        {{ report?.llm_generated ? 'Spark Lite 已生成建议' : '规则算法 / 模板建议' }}
      </el-tag>
    </header>

    <section class="control-panel">
      <el-form :inline="true" label-position="top" class="match-form">
        <el-form-item label="简历">
          <el-select v-model="selectedResumeId" placeholder="选择简历" class="select">
            <el-option
              v-for="resume in options.resumes"
              :key="resume.id"
              :label="resume.name"
              :value="resume.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标岗位">
          <el-select v-model="selectedJobId" placeholder="选择岗位" class="select">
            <el-option
              v-for="job in options.jobs"
              :key="job.id"
              :label="job.title"
              :value="job.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="学习周期（月）">
          <el-input-number v-model="targetMonths" :min="1" :max="24" controls-position="right" />
        </el-form-item>
        <el-form-item label=" ">
          <el-button type="primary" :loading="loading.match" @click="runMatch">开始诊断</el-button>
          <el-button :loading="loading.multi" @click="runMultiMatch">多岗位对比</el-button>
        </el-form-item>
      </el-form>
    </section>

    <el-alert
      v-if="error"
      class="message"
      type="error"
      :title="error"
      show-icon
      :closable="false"
    />

    <section v-if="report" class="summary-layout">
      <div class="score-panel">
        <div class="score-ring" :style="{ '--score': report.total_score }">
          <span class="score-value">{{ report.total_score }}</span>
          <span class="score-label">综合匹配</span>
        </div>
        <div class="score-copy">
          <el-tag :type="levelType(report.assessment_level)" size="large">
            {{ report.assessment_level }}
          </el-tag>
          <h3>{{ report.resume_name }} → {{ report.job_title }}</h3>
          <p>{{ report.overall_assessment }}</p>
        </div>
      </div>

      <div class="dimension-panel">
        <div v-for="dimension in report.dimensions" :key="dimension.dimension" class="dimension-row">
          <div class="dimension-head">
            <span>{{ dimension.label }}</span>
            <strong>{{ dimension.score }}</strong>
          </div>
          <el-progress :percentage="dimension.score" :stroke-width="10" :show-text="false" />
          <p>{{ dimension.explanation }}</p>
        </div>
      </div>
    </section>

    <section v-if="report" class="content-grid">
      <div class="section">
        <div class="section-title">
          <h3>差距分析</h3>
          <el-button text type="primary" :loading="loading.gap" @click="loadGap">刷新</el-button>
        </div>
        <p v-if="gapReport?.summary" class="section-note">{{ gapReport.summary }}</p>
        <el-tabs v-model="gapTab" class="gap-tabs">
          <el-tab-pane label="缺失" name="missing" />
          <el-tab-pane label="匹配" name="matched" />
          <el-tab-pane label="过剩" name="surplus" />
        </el-tabs>
        <el-table :data="filteredGaps" height="320" empty-text="暂无差距项">
          <el-table-column prop="skill_name" label="能力项" min-width="120" />
          <el-table-column prop="importance" label="重要性" width="90">
            <template #default="{ row }">
              <el-tag :type="row.importance === 'required' ? 'danger' : 'info'" size="small">
                {{ row.importance === 'required' ? '必备' : '加分' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="required_level" label="目标水平" width="100" />
          <el-table-column prop="suggestion" label="建议" min-width="220" />
        </el-table>
      </div>

      <div class="section">
        <div class="section-title">
          <h3>改进建议</h3>
        </div>
        <ul class="recommendations">
          <li v-for="item in report.recommendations" :key="item">{{ item }}</li>
        </ul>
      </div>
    </section>

    <section v-if="learningPath" class="section">
      <div class="section-title">
        <h3>学习路径</h3>
        <el-tag :type="learningPath.llm_generated ? 'success' : 'info'" effect="plain">
          {{ learningPath.total_months }} 个月 · {{ learningPath.llm_generated ? 'Spark Lite' : '模板' }}
        </el-tag>
      </div>
      <div class="timeline">
        <article v-for="phase in learningPath.phases" :key="phase.phase" class="phase">
          <div class="phase-index">{{ phase.phase }}</div>
          <h4>{{ phase.title }}</h4>
          <p>{{ phase.duration_weeks }} 周</p>
          <div class="tag-list">
            <el-tag v-for="topic in phase.topics" :key="topic" effect="plain">{{ topic }}</el-tag>
          </div>
          <ul>
            <li v-for="milestone in phase.milestones" :key="milestone">{{ milestone }}</li>
          </ul>
        </article>
      </div>
    </section>

    <section v-if="comparison" class="section">
      <div class="section-title">
        <h3>多岗位对比</h3>
        <span>{{ comparison.recommendation }}</span>
      </div>
      <el-table :data="comparison.comparisons" empty-text="暂无对比结果">
        <el-table-column prop="job_title" label="岗位" min-width="180" />
        <el-table-column prop="match_score" label="匹配分" width="100" />
        <el-table-column prop="assessment_level" label="判断" width="120" />
        <el-table-column label="优势" min-width="180">
          <template #default="{ row }">{{ row.advantages.join('、') || '待补充证据' }}</template>
        </el-table-column>
        <el-table-column label="短板" min-width="180">
          <template #default="{ row }">{{ row.disadvantages.join('、') || '暂无明显短板' }}</template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import matchingApi from '../api/matching'

const options = reactive({ resumes: [], jobs: [] })
const selectedResumeId = ref('')
const selectedJobId = ref('')
const targetMonths = ref(6)
const report = ref(null)
const gapReport = ref(null)
const learningPath = ref(null)
const comparison = ref(null)
const gapTab = ref('missing')
const error = ref('')
const loading = reactive({ options: false, match: false, gap: false, path: false, multi: false })

const filteredGaps = computed(() => {
  if (!gapReport.value) return []
  return gapReport.value.skill_gaps.filter((item) => item.status === gapTab.value)
})

onMounted(async () => {
  await loadOptions()
})

async function loadOptions() {
  loading.options = true
  error.value = ''
  try {
    const data = await matchingApi.options()
    options.resumes = data.resumes
    options.jobs = data.jobs
    selectedResumeId.value = data.resumes[0]?.id || ''
    selectedJobId.value = data.jobs[0]?.id || ''
  } catch (err) {
    error.value = '加载简历或岗位数据失败，请确认后端服务已启动。'
  } finally {
    loading.options = false
  }
}

async function runMatch() {
  if (!selectedResumeId.value || !selectedJobId.value) return
  loading.match = true
  error.value = ''
  try {
    report.value = await matchingApi.match({
      resume_id: selectedResumeId.value,
      job_id: selectedJobId.value,
    })
    comparison.value = null
    await Promise.all([loadGap(), loadLearningPath()])
  } catch (err) {
    error.value = '匹配诊断失败，请检查后端接口或请求参数。'
  } finally {
    loading.match = false
  }
}

async function loadGap() {
  if (!selectedResumeId.value || !selectedJobId.value) return
  loading.gap = true
  try {
    gapReport.value = await matchingApi.gapAnalysis({
      resume_id: selectedResumeId.value,
      job_id: selectedJobId.value,
    })
  } finally {
    loading.gap = false
  }
}

async function loadLearningPath() {
  if (!selectedResumeId.value || !selectedJobId.value) return
  loading.path = true
  try {
    learningPath.value = await matchingApi.learningPath({
      resume_id: selectedResumeId.value,
      job_id: selectedJobId.value,
      target_months: targetMonths.value,
    })
  } finally {
    loading.path = false
  }
}

async function runMultiMatch() {
  if (!selectedResumeId.value || options.jobs.length < 2) return
  loading.multi = true
  error.value = ''
  try {
    comparison.value = await matchingApi.multiMatch({
      resume_id: selectedResumeId.value,
      job_ids: options.jobs.map((job) => job.id),
    })
  } catch (err) {
    error.value = '多岗位对比失败，请稍后重试。'
  } finally {
    loading.multi = false
  }
}

function levelType(level) {
  if (level === '高度匹配') return 'success'
  if (level === '基本匹配') return 'primary'
  if (level === '存在明显差距') return 'warning'
  return 'danger'
}
</script>

<style scoped>
.page {
  animation: fadeIn .3s ease;
  color: #0f172a;
}
.page-header,
.section-title,
.score-panel,
.dimension-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-header {
  margin-bottom: 18px;
}
.page-title {
  margin: 0;
  font-size: 22px;
}
.page-subtitle {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}
.control-panel,
.section,
.score-panel,
.dimension-panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, .04);
}
.control-panel {
  padding: 16px 18px 0;
  margin-bottom: 16px;
}
.match-form {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
}
.select {
  width: 260px;
}
.message {
  margin-bottom: 16px;
}
.summary-layout {
  display: grid;
  grid-template-columns: minmax(280px, .9fr) minmax(360px, 1.1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.score-panel {
  padding: 22px;
  justify-content: flex-start;
}
.score-ring {
  width: 132px;
  height: 132px;
  border-radius: 50%;
  display: grid;
  place-content: center;
  text-align: center;
  background: conic-gradient(#2563eb calc(var(--score, 76) * 1%), #e2e8f0 0);
  position: relative;
}
.score-ring::after {
  content: "";
  position: absolute;
  inset: 10px;
  background: #fff;
  border-radius: 50%;
}
.score-value,
.score-label {
  position: relative;
  z-index: 1;
}
.score-value {
  font-size: 34px;
  font-weight: 800;
  color: #1d4ed8;
}
.score-label {
  font-size: 12px;
  color: #64748b;
}
.score-copy h3 {
  margin: 12px 0 8px;
  font-size: 18px;
}
.score-copy p,
.dimension-row p,
.section-note {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}
.dimension-panel {
  padding: 16px 18px;
}
.dimension-row + .dimension-row {
  margin-top: 14px;
}
.dimension-head strong {
  color: #2563eb;
}
.content-grid {
  display: grid;
  grid-template-columns: minmax(420px, 1.4fr) minmax(280px, .8fr);
  gap: 16px;
  margin-bottom: 16px;
}
.section {
  padding: 18px;
  margin-bottom: 16px;
}
.section-title {
  margin-bottom: 12px;
}
.section-title h3 {
  margin: 0;
  font-size: 17px;
}
.section-title span {
  color: #64748b;
  font-size: 13px;
}
.gap-tabs {
  margin-top: 8px;
}
.recommendations {
  margin: 0;
  padding-left: 18px;
  color: #334155;
  line-height: 1.9;
}
.timeline {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.phase {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  min-height: 220px;
}
.phase-index {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #2563eb;
  color: #fff;
  font-weight: 700;
}
.phase h4 {
  margin: 12px 0 4px;
}
.phase p {
  margin: 0 0 10px;
  color: #64748b;
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.phase ul {
  margin: 12px 0 0;
  padding-left: 18px;
  color: #334155;
  line-height: 1.7;
}
@media (max-width: 980px) {
  .summary-layout,
  .content-grid,
  .timeline {
    grid-template-columns: 1fr;
  }
  .select {
    width: min(100%, 320px);
  }
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
