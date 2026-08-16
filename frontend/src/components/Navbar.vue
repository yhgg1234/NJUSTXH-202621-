<template>
  <nav class="navbar">
    <div class="nav-brand">
      <router-link to="/" class="brand-link">
        <span class="brand-code">XH-202621</span>
        <span class="brand-title">岗位能力图谱系统</span>
      </router-link>
    </div>
    <div class="nav-links">
      <router-link to="/data-collection">数据采集</router-link>
      <router-link to="/data-cleaning">数据清洗</router-link>
      <router-link to="/extraction">信息抽取</router-link>
      <router-link to="/knowledge-graph">知识图谱</router-link>
      <router-link to="/jobs">岗位管理</router-link>
      <router-link to="/job-evolution">岗位演化</router-link>
      <router-link to="/new-job-discovery">趋势洞察</router-link>
      <router-link to="/resume">简历解析</router-link>
      <router-link to="/matching">人岗匹配</router-link>
    </div>
  </nav>
</template>

<script setup>
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
  margin-bottom: 20px;
}
.brand-link {
  text-decoration: none;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.brand-code {
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .15em;
}
.brand-title {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}
.nav-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.nav-links a {
  text-decoration: none;
  padding: 6px 14px;
  border-radius: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  transition: all .2s;
}
.nav-links a:hover {
  color: #2563eb;
  background: #eff6ff;
}
.nav-links a.router-link-exact-active {
  color: #fff;
  background: #2563eb;
}
@media (max-width: 768px) {
  .navbar { flex-direction: column; align-items: flex-start; }
  .nav-links { overflow-x: auto; width: 100%; }
}
</style>
