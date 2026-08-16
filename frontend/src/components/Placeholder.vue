<template>
  <div class="placeholder-card">
    <div class="placeholder-icon">{{ icon }}</div>
    <h3 class="placeholder-title">{{ title }}</h3>
    <p class="placeholder-desc">{{ description }}</p>
    <div v-if="visualizations && visualizations.length" class="placeholder-viz">
      <span class="viz-label">预留可视化组件：</span>
      <el-tag v-for="viz in visualizations" :key="viz" size="small" type="info" effect="plain" style="margin: 2px 4px">
        {{ viz }}
      </el-tag>
    </div>
    <el-divider />
    <p class="placeholder-status">状态：接口已定义，功能待实现</p>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: '📦' },
  title: { type: String, default: '功能模块' },
  description: { type: String, default: '该功能模块接口已定义，业务逻辑待实现。' },
  visualizations: { type: Array, default: () => [] },
})
</script>

<style scoped>
.placeholder-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px 30px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.placeholder-icon { font-size: 48px; margin-bottom: 16px; }
.placeholder-title { font-size: 20px; color: #0f172a; margin: 0 0 8px; }
.placeholder-desc { font-size: 14px; color: #64748b; margin: 0 0 20px; max-width: 500px; margin-inline: auto; }
.placeholder-viz { margin-bottom: 16px; }
.viz-label { font-size: 12px; color: #94a3b8; }
.placeholder-status { font-size: 12px; color: #94a3b8; margin: 0; }
</style>
