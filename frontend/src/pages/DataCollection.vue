<template>
  <div class="page">
    <h2 class="page-title">🔍 数据采集</h2>
    <Placeholder
      icon="🕷️"
      title="多源异构数据采集"
      description="管理数据源注册（搜索引擎/招聘平台/企业DB/行业报告），创建和调度采集任务，浏览原始采集数据。支持定时调度和批量采集。"
      :visualizations="['数据源管理面板', '采集任务配置表单', '原始数据列表（分页）']"
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
