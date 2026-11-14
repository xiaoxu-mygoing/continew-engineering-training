import http from '@/utils/http'

export interface TrainingDocument {
  documentId: string
  version: number
  fileName: string
  fileSize: number
  indexState: 'ready' | 'pending' | 'failed'
  indexError?: string
  updatedAt: string
}

const base = '/training/documents'

export interface DocumentAnswer {
  workflow?: { route: 'answered' | 'unverified' | 'no_match', documents: number, candidates: number, citations: number }
  answer: string
  sources: { documentId: string, version: number, fileName: string, chunk: number, page?: number, text: string }[]
}

export const askDocument = (doc: TrainingDocument, question: string) =>
  http.post<DocumentAnswer>(`${base}/${doc.documentId}/ask`, { version: doc.version, question }, { timeout: 225000 })

export const askLibrary = (question: string) =>
  http.post<DocumentAnswer>(`${base}/ask`, { question }, { timeout: 225000 })

export const retryIndex = (doc: TrainingDocument) =>
  http.post(`${base}/${doc.documentId}/index`, undefined, { params: { version: doc.version } })

export const listDocuments = () => http.get<TrainingDocument[]>(base)

export function saveDocument(file: File, original?: TrainingDocument) {
  const form = new FormData()
  form.append('file', file)
  if (original) {
    return http.put(`${base}/${original.documentId}`, form, { params: { version: original.version } })
  }
  return http.post<string>(base, form)
}

export const downloadDocument = (doc: TrainingDocument) =>
  http.download(`${base}/${doc.documentId}/content`, { version: doc.version })

export const deleteDocument = (doc: TrainingDocument) =>
  http.del(`${base}/${doc.documentId}`, undefined, { params: { version: doc.version } })
