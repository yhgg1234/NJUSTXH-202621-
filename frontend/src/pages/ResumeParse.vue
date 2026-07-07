<template>
  <div class="page">
    <h2 class="page-title">📄 简历解析</h2>
    <Placeholder
      icon="📤"
      title="简历上传与智能解析"
      description="支持PDF/DOCX简历文件上传，利用大模型（LayoutLM/讯飞星火）进行结构化信息抽取：基本信息、教育/工作/项目经历、技能/证书/语言能力。"
      :visualizations="['拖拽上传区域', '解析结果结构化卡片', '简历列表（分页/筛选）', '原始文件预览']"
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
