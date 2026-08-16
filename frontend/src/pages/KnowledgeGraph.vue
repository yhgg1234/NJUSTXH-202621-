<template>
  <div class="page">
    <h2 class="page-title">🕸️ 知识图谱</h2>
    <KnowledgeGraph />
  </div>
</template>

<script setup>
import KnowledgeGraph from '../components/KnowledgeGraph.vue'
</script>

<style scoped>
.page { animation: fadeIn .3s ease; }
.page-title { margin: 0 0 20px; font-size: 22px; color: #0f172a; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
</style>
