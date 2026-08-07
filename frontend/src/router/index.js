import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../pages/Dashboard.vue'),
    meta: { title: '仪表盘' },
  },
  {
    path: '/data-collection',
    name: 'DataCollection',
    component: () => import('../pages/DataCollection.vue'),
    meta: { title: '数据采集' },
  },
  {
    path: '/data-cleaning',
    name: 'DataCleaning',
    component: () => import('../pages/DataCleaning.vue'),
    meta: { title: '数据清洗' },
  },
  {
    path: '/extraction',
    name: 'Extraction',
    component: () => import('../pages/Extraction.vue'),
    meta: { title: '信息抽取' },
  },
  {
    path: '/knowledge-graph',
    name: 'KnowledgeGraph',
    component: () => import('../pages/KnowledgeGraph.vue'),
    meta: { title: '知识图谱' },
  },
  {
    path: '/jobs',
    name: 'JobSearch',
    component: () => import('../pages/JobSearch.vue'),
    meta: { title: '岗位管理' },
  },
  {
    path: '/new-job-discovery',
    name: 'NewJobDiscovery',
    component: () => import('../pages/NewJobDiscovery.vue'),
    meta: { title: '岗位趋势洞察' },
  },
  {
    path: '/job-evolution',
    name: 'JobEvolution',
    component: () => import('../pages/JobEvolution.vue'),
    meta: { title: '岗位演化' },
  },
  {
    path: '/resume',
    name: 'ResumeParse',
    component: () => import('../pages/ResumeParse.vue'),
    meta: { title: '简历解析' },
  },
  {
    path: '/matching',
    name: 'MatchReport',
    component: () => import('../pages/MatchReport.vue'),
    meta: { title: '人岗匹配' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
