import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface Tenant {
  tenant_id: string
  name: string
  created_at: string
}

export interface Document {
  doc_id: string
  tenant_id: string
  filename: string | null
  file_type: string | null
  file_size: number | null
  source: string | null
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface SearchResultItem {
  chunk_id: string
  doc_id: string
  text: string
  score: number
  metadata: Record<string, any>
}

export const tenantApi = {
  list: () => api.get<Tenant[]>('/tenants'),
  create: (data: { tenant_id?: string; name: string }) => api.post<Tenant>('/tenants', data),
  delete: (tenantId: string) => api.delete(`/tenants/${tenantId}`),
}

export const documentApi = {
  list: (tenantId: string) => api.get<Document[]>(`/tenants/${tenantId}/documents`),
  upload: (tenantId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<Document>(`/tenants/${tenantId}/documents/upload`, form)
  },
  addText: (tenantId: string, data: { text: string; source?: string }) =>
    api.post<Document>(`/tenants/${tenantId}/documents/text`, data),
  delete: (tenantId: string, docId: string) =>
    api.delete(`/tenants/${tenantId}/documents/${docId}`),
}

export const searchApi = {
  search: (tenantId: string, data: { query: string; top_k?: number }) =>
    api.post<SearchResultItem[]>(`/tenants/${tenantId}/search`, data),
}
