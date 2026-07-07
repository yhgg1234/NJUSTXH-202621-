import apiClient from './client'

export default {
  extractEntities: (data) => apiClient.post('/extraction/entities/extract', data),
  extractRelations: (data) => apiClient.post('/extraction/relations/extract', data),
  alignEntities: (data) => apiClient.post('/extraction/entities/align', data),
  listAlignHistory: (params) => apiClient.get('/extraction/entities/align/history', { params }),
  getOntology: () => apiClient.get('/extraction/ontology'),
  updateOntology: (data) => apiClient.put('/extraction/ontology', data),
  listOntologyEntities: () => apiClient.get('/extraction/ontology/entities'),
  listOntologyRelations: () => apiClient.get('/extraction/ontology/relations'),
}
