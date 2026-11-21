import http from '@/utils/http'

export interface FaceStatus {
  bound: boolean
  identificationEnabled: boolean
  templateVersion: number
  updatedAt?: string
}

const url = '/user/face'
export const getFaceStatus = () => http.get<FaceStatus>(url)
export const checkFaceQuality = (image: string) => http.post<{ hint: string }>(`${url}/quality`, { image })
export const bindFace = (password: string, version: number, image: string) =>
  http.put<FaceStatus>(url, { password, version, image })
export const unbindFace = (password: string, version: number) =>
  http.del<FaceStatus>(url, { password, version })
export const setIdentification = (enabled: boolean, password: string, version: number) =>
  http.put<FaceStatus>(`${url}/identification/${enabled}`, { password, version })

export interface LivenessContext {
  clientId: string
  identify: boolean
  username?: string
}

export interface LivenessChallenge {
  challengeId: string
  actions: ('blink' | 'mouth')[]
  expiresIn: number
}

export const startLiveness = (context: LivenessContext, tenant: string, signal: AbortSignal) =>
  http.post<LivenessChallenge>('/auth/face/liveness/challenge', context, {
    headers: tenant ? { 'X-Tenant-Code': tenant } : {},
    signal,
  })

export const verifyLiveness = (challengeId: string, context: LivenessContext, batches: string[][], tenant: string, signal: AbortSignal) =>
  http.post<{ livenessToken: string, expiresIn: number }>('/auth/face/liveness/verify', { challengeId, context, batches }, {
    headers: tenant ? { 'X-Tenant-Code': tenant } : {},
    signal,
    timeout: 70000,
  })
