<template>
  <div class="page">
    <h2 class="page-title">📅 岗位演化</h2>
    <Placeholder
      icon="🔮"
      title="岗位动态演化分析"
      description="分析岗位技能组成随时间的变化趋势，发现新增/衰退的技能，预测未来6个月的热门技能方向。支持按季度/月度粒度查看。"
      :visualizations="['演化时间线（ECharts 河流图）', '技能变化对比（新增/移除/增强/减弱）', '趋势热力矩阵', '未来预测雷达图']"
    />
  </div>
</template>

<script setup>
import Placeholder from '../components/Placeholder.vue'
</script>

<style scoped>
.page { animation: fadeIn .3s ease; }
.page-title { margin: 0 0 20px; font-size: 22px; color: #0f172a; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
