import apiClient from './client'

export default {
  upload: (formData) => apiClient.post('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  batchUpload: (formData) => apiClient.post('/resume/upload/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  listResumes: (params) => apiClient.get('/resume/', { params }),
  getResume: (id) => apiClient.get(`/resume/${id}`),
  deleteResume: (id) => apiClient.delete(`/resume/${id}`),
}
