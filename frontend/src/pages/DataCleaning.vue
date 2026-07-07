<template>
  <div class="page">
    <h2 class="page-title">🧹 数据清洗</h2>
    <Placeholder
      icon="🧽"
      title="数据清洗管线"
      description="配置清洗管线（SimHash/MinHash去重、噪声过滤、文本规范化），触发清洗任务，人工校验低置信度条目，管理清洗后的高质量数据集。"
      :visualizations="['管线配置面板', '清洗任务进度条', '人工校验工作台', '数据集浏览（分页）']"
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
