import apiClient from './client'

export default {
  demoOptions: () => apiClient.get('/matching/demo-options'),
  match: (data) => apiClient.post('/matching/match', data),
  getMatchReport: (id) => apiClient.get(`/matching/match/${id}`),
  multiMatch: (data) => apiClient.post('/matching/multi-match', data),
  gapAnalysis: (data) => apiClient.post('/matching/gap-analysis', data),
  learningPath: (data) => apiClient.post('/matching/learning-path', data),
  listHistory: (params) => apiClient.get('/matching/history', { params }),
}
