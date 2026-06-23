<template>
  <div id="app">
    <header class="app-header">
      <div>
        <p class="project-code">XH-202621</p>
        <h1>岗位能力图谱系统</h1>
      </div>
      <p>多源异构数据驱动 · 大模型抽取 · 动态演化分析</p>
    </header>
    <main>
      <KnowledgeGraph />
    </main>
  </div>
</template>

<script setup>
import KnowledgeGraph from './components/KnowledgeGraph.vue'
</script>

<style>
* { box-sizing: border-box; }
body { margin: 0; color: #1e293b; background: #eef2f7; font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif; }
#app { max-width: 1440px; margin: 0 auto; padding: 30px; }
.app-header { display: flex; align-items: end; justify-content: space-between; gap: 30px; margin-bottom: 24px; }
.app-header h1 { margin: 0; color: #0f172a; font-size: 30px; letter-spacing: -.03em; }
.app-header > p { margin: 0 0 5px; color: #64748b; font-size: 13px; }
.project-code { margin: 0 0 4px; color: #2563eb; font-size: 11px; font-weight: 800; letter-spacing: .18em; }
@media (max-width: 700px) { #app { padding: 16px; } .app-header { align-items: flex-start; flex-direction: column; } }
</style>
