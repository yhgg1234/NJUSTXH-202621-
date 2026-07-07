<template>
  <div class="page">
    <h2 class="page-title">💼 岗位管理</h2>
    <Placeholder
      icon="📋"
      title="岗位定义与检索"
      description="定义和编辑岗位信息（技能要求、学历、经验、技术栈、证书），支持多维检索筛选，管理岗位生命周期。"
      :visualizations="['岗位列表（分页/筛选）', '岗位编辑表单', '技能标签管理', '新岗位发现结果卡片']"
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
