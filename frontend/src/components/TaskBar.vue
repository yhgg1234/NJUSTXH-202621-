<template>
  <footer class="system-map">
    <div class="map-heading">
      <span class="map-mark">◇</span>
      <div>
        <strong>系统能力全景</strong>
        <small>岗位知识与人才画像协同驱动智能决策</small>
      </div>
    </div>

    <div class="map-lanes">
      <section class="lane" aria-label="岗位知识链">
        <span class="lane-label">岗位知识链</span>
        <div class="lane-flow">
          <router-link to="/data-collection" :class="{ active: isActive('/data-collection') }">多源采集</router-link>
          <i>→</i>
          <router-link to="/data-cleaning" :class="{ active: isActive('/data-cleaning') }">数据治理</router-link>
          <i>→</i>
          <router-link to="/extraction" :class="{ active: isActive('/extraction') }">信息抽取</router-link>
          <i>→</i>
          <router-link to="/knowledge-graph" :class="{ active: isActive('/knowledge-graph', '/jobs') }">知识图谱</router-link>
          <i>→</i>
          <router-link to="/new-job-discovery" :class="{ active: isActive('/job-evolution', '/new-job-discovery') }">岗位洞察</router-link>
        </div>
      </section>

      <section class="lane decision-lane" aria-label="人才决策链">
        <span class="lane-label">人才决策链</span>
        <div class="lane-flow">
          <router-link to="/knowledge-graph" :class="{ active: isActive('/knowledge-graph', '/jobs', '/job-evolution', '/new-job-discovery') }">岗位知识</router-link>
          <b>＋</b>
          <router-link to="/resume" :class="{ active: isActive('/resume') }">简历画像</router-link>
          <i>→</i>
          <router-link to="/matching" class="decision-node" :class="{ active: isActive('/matching') }">人岗智能匹配</router-link>
        </div>
      </section>
    </div>
  </footer>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

function isActive(...paths) {
  return paths.includes(route.path)
}
</script>

<style scoped>
.system-map {
  display: grid;
  overflow: hidden;
  grid-template-columns: 230px minmax(0, 1fr);
  gap: 24px;
  margin-top: 20px;
  padding: 17px 20px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: rgba(255, 255, 255, .88);
  box-shadow: 0 4px 18px rgba(15, 23, 42, .04);
}
.map-heading { display: flex; align-items: center; gap: 10px; }
.map-heading strong, .map-heading small { display: block; }
.map-heading strong { color: #334155; font-size: 12px; }
.map-heading small { margin-top: 4px; color: #94a3b8; font-size: 10px; line-height: 1.45; }
.map-mark { display: grid; width: 30px; height: 30px; flex: 0 0 auto; place-items: center; border-radius: 9px; color: #2563eb; background: #eff6ff; font-size: 18px; font-weight: 800; }
.map-lanes { display: grid; gap: 9px; }
.lane { display: grid; grid-template-columns: 72px minmax(0, 1fr); align-items: center; gap: 10px; }
.lane-label { color: #94a3b8; font-size: 10px; font-weight: 700; white-space: nowrap; }
.lane-flow { display: flex; align-items: center; gap: 7px; min-width: 0; }
.lane-flow a { padding: 5px 9px; border: 1px solid transparent; border-radius: 7px; color: #64748b; background: #f8fafc; font-size: 10px; font-weight: 650; text-decoration: none; white-space: nowrap; transition: .18s ease; }
.lane-flow a:hover { border-color: #bfdbfe; color: #1d4ed8; background: #eff6ff; }
.lane-flow a.active { border-color: #bfdbfe; color: #1d4ed8; background: #dbeafe; box-shadow: 0 2px 7px rgba(37, 99, 235, .1); }
.lane-flow a.decision-node { border-color: #cbd5e1; color: #475569; background: #f1f5f9; font-weight: 750; }
.lane-flow a.decision-node.active { border-color: #2563eb; color: #fff; background: #2563eb; box-shadow: 0 2px 7px rgba(37, 99, 235, .16); }
.lane-flow i, .lane-flow b { color: #cbd5e1; font-size: 10px; font-style: normal; font-weight: 500; }
.decision-lane { padding-top: 8px; border-top: 1px dashed #e2e8f0; }
@media (max-width: 1000px) {
  .system-map { grid-template-columns: 1fr; gap: 14px; }
  .map-lanes { overflow-x: auto; padding-bottom: 3px; }
  .lane { min-width: 650px; }
}
@media (max-width: 600px) {
  .system-map { padding: 15px; }
}
</style>
