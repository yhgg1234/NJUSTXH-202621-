<template>
  <div class="page">
    <h2 class="page-title">🧠 信息抽取</h2>
    <Placeholder
      icon="🏷️"
      title="大模型驱动的信息抽取"
      description="基于LLM+RAG进行NER实体抽取（7类实体）、关系抽取（8种关系）、实体对齐（BERT语义/规则/混合），管理本体Schema定义。支持批量处理和结果展示。"
      :visualizations="['文本输入+实体类型选择', '抽取结果高亮展示', '关系图谱预览', '本体Schema编辑', '实体对齐对比视图']"
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
