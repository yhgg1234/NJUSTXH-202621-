<template>
  <div class="page">
    <h2 class="page-title">🎯 人岗匹配</h2>
    <Placeholder
      icon="🤝"
      title="多维度人岗匹配诊断"
      description="选择简历和目标岗位进行匹配分析，输出4维度得分（技能/经验/学历/行业），识别差距项，生成个性化学习路径规划，支持多岗位对比。"
      :visualizations="['简历-岗位选择器', '匹配得分雷达图', '逐技能对比表（missing/matched/surplus）', '学习路径时间轴', '多岗位对比排行']"
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
