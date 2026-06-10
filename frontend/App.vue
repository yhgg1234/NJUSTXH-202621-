<!--
  XH-202621 岗位能力图谱系统前端入口
  运行 `npm install` 后 `npm run dev` 启动开发服务
-->

<template>
  <div id="app">
    <header class="app-header">
      <h1>岗位能力图谱系统</h1>
      <p class="subtitle">XH-202621 多源异构数据驱动的岗位和能力图谱构建与动态演化分析</p>
    </header>
    <main class="app-main">
      <div class="status-card">
        <h2>系统状态</h2>
        <p>前端服务已启动 ✓</p>
        <p>后端 API：待连接</p>
        <p>Neo4j 图谱：待连接</p>
      </div>
      <nav class="module-nav">
        <h3>功能模块</h3>
        <ul>
          <li>数据采集与清洗</li>
          <li>新岗位发现与定义</li>
          <li>既有岗位能力动态更新</li>
          <li>岗位能力全景图谱</li>
          <li>简历解析与人岗匹配</li>
          <li>动态演化分析</li>
        </ul>
      </nav>
    </main>
  </div>
</template>

<script>
export default {
  name: 'App',
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f5f7fa;
  color: #333;
}

#app {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px 20px;
}

.app-header h1 {
  font-size: 28px;
  color: #1a1a2e;
}

.app-header .subtitle {
  font-size: 14px;
  color: #666;
  margin-top: 8px;
}

.app-main {
  margin-top: 32px;
  display: flex;
  gap: 24px;
}

.status-card,
.module-nav {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.status-card h2,
.module-nav h3 {
  margin-bottom: 16px;
  color: #1a1a2e;
}

.status-card p {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.module-nav ul {
  list-style: none;
}

.module-nav li {
  padding: 10px 12px;
  margin-bottom: 6px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 14px;
}
</style>
