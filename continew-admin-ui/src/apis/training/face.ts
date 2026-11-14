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
