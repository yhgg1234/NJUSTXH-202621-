<template>
  <div class="dashboard">
    <h2 class="page-title">📊 系统仪表盘</h2>
    <div class="stats-grid">
      <div class="stat-card" v-for="stat in stats" :key="stat.label">
        <div class="stat-value">--</div>
        <div class="stat-label">{{ stat.label }}</div>
      </div>
    </div>
    <Placeholder
      icon="📈"
      title="统计概览"
      description="展示岗位总数、简历总数、图谱实体/关系数、匹配记录数等核心指标，以及热门技能排行和趋势变化图。"
      :visualizations="['ECharts 柱状图 — 实体类型分布', 'ECharts 折线图 — 岗位增长趋势', 'ECharts 饼图 — 行业分布', 'ECharts 词云 — 热门技能']"
    />
  </div>
</template>

<script setup>
import Placeholder from '../components/Placeholder.vue'

const stats = [
  { label: '岗位总数' },
  { label: '简历总数' },
  { label: '图谱实体' },
  { label: '图谱关系' },
  { label: '数据源' },
  { label: '匹配记录' },
]
</script>

<style scoped>
.dashboard { animation: fadeIn .3s ease; }
.page-title { margin: 0 0 20px; font-size: 22px; color: #0f172a; }
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px 20px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.stat-value { font-size: 32px; font-weight: 700; color: #2563eb; }
.stat-label { font-size: 13px; color: #64748b; margin-top: 6px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
