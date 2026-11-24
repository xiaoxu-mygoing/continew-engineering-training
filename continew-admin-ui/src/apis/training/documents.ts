import http from '@/utils/http'

export type BuildMode = 'rag' | 'graph' | 'both'

export interface TrainingDocument {
  buildMode: BuildMode
  documentId: string
  version: number
  fileName: string
  fileSize: number
  indexState: 'ready' | 'pending' | 'failed' | 'disabled'
  indexError?: string
  graphState: 'ready' | 'pending' | 'failed' | 'disabled'
  graphError?: string
  updatedAt: string
}

const base = '/training/documents'

export interface DocumentSource {
  documentId: string
  version: number
  fileName: string
  chunk: number
  page?: number
  text: string
}

export interface DocumentAnswer {
  workflow?: { route: 'answered' | 'unverified' | 'no_match' | 'general', documents: number, candidates: number, citations: number }
  answer: string
  sources: DocumentSource[]
}

export interface GraphNode {
  id: string
  name: string
  kind: string
}

export interface GraphEdge {
  id: number
  source: string
  target: string
  predicate: string
  chunk?: number
  page?: number
  evidence: string
  documentId?: string
  version?: number
  fileName?: string
}

export interface GraphPath {
  from: string
  to: string
  predicate: string
}

export interface GraphAnswer {
  answer: string
  sources: DocumentSource[]
  nodes: GraphNode[]
  edges: GraphEdge[]
  path: GraphPath[]
  workflow?: { route: 'answered' | 'unverified' | 'no_match', documents: number, nodes: number, edges: number }
}

export interface DocumentGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphStats {
  entityCount: number
  relationCount: number
  documentCount: number
}

export const searchLibrary = (query: string) =>
  http.post<{ results: DocumentSource[] }>(`${base}/search`, { query }, { timeout: 90000 })

export const fetchLibraryGraphStats = () => http.get<GraphStats>('/training/graph/overview')

export const fetchLibraryGraph = () =>
  http.get<DocumentGraph>('/training/graph/overview', { includeGraph: true }, { timeout: 70000 })

export const askDocument = (doc: TrainingDocument, question: string) =>
  http.post<DocumentAnswer>(`${base}/${doc.documentId}/ask`, { version: doc.version, question }, { timeout: 225000 })

export const askLibrary = (question: string) =>
  http.post<DocumentAnswer>(`${base}/ask`, { question }, { timeout: 270000 })

export const askGraph = (question: string, doc?: TrainingDocument) =>
  http.post<GraphAnswer>('/training/graph/ask', { question, documentId: doc?.documentId, version: doc?.version }, { timeout: 240000 })

export const fetchDocumentGraph = (doc: TrainingDocument) =>
  http.get<DocumentGraph>(`/training/graph/${doc.documentId}`, { version: doc.version }, { timeout: 60000 })

export const retryIndex = (doc: TrainingDocument) =>
  http.post(`${base}/${doc.documentId}/index`, undefined, { params: { version: doc.version } })

export const listDocuments = () => http.get<TrainingDocument[]>(base)

export function saveDocument(file: File, original?: TrainingDocument, mode?: BuildMode) {
  const form = new FormData()
  form.append('file', file)
  if (original) {
    return http.put(`${base}/${original.documentId}`, form, { params: { version: original.version, mode } })
  }
  return http.post<string>(base, form, { params: { mode: mode || 'both' } })
}

export const downloadDocument = (doc: TrainingDocument) =>
  http.download(`${base}/${doc.documentId}/content`, { version: doc.version })

export const deleteDocument = (doc: TrainingDocument) =>
  http.del(`${base}/${doc.documentId}`, undefined, { params: { version: doc.version } })
