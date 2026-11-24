// Access Token 只保存在当前页面进程内，避免 XSS 后长期凭证从 localStorage 被直接读取。
// 页面重载后的登录态由 HttpOnly Refresh Token Cookie 恢复。
let accessToken: string | null = null
let authGeneration = 0
const accessTokenEvents = new EventTarget()
const ACCESS_TOKEN_CHANGE_EVENT = 'change'
const TAB_SESSION_KEY = 'continew-tab-session-id'
let tabSessionId: string | undefined

class SessionChangedError extends Error {
  constructor() {
    super('此浏览器中的登录账号已切换，请在当前窗口重新登录。')
  }
}

const isLogin = () => {
  return !!accessToken
}

const getAccessToken = () => {
  return accessToken
}

/** 当前认证代次；每次 Access Token 变更都会递增，用于忽略迟到的认证失败响应。 */
const getAuthGeneration = () => {
  return authGeneration
}

/**
 * 读取 Access Token 绑定的登录会话 ID（JWT 中的 sid 声明）。
 * 用于前端展示和续签时校验会话一致性，服务端仍独立校验令牌及操作人。
 */
const getSessionId = (token = accessToken): string | undefined => {
  const payload = token?.split('.')[1]
  if (!payload) return undefined
  try {
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    // 只按 ASCII 模式匹配 sid，避免解码载荷中可能存在的非 UTF-8 字节。
    return atob(base64).match(/"sid"\s*:\s*"([^"]+)"/)?.[1]
  } catch {
    return undefined
  }
}

const setAccessToken = (value: string) => {
  tabSessionId = getSessionId(value)
  // 仅记录标签页已选定的会话标识，访问令牌继续只保存在内存中。
  try {
    if (tabSessionId) sessionStorage.setItem(TAB_SESSION_KEY, tabSessionId)
  } catch {
    // 存储受限时仍可检查当前页面内的续签。
  }
  if (accessToken !== value) {
    authGeneration += 1
  }
  accessToken = value
  accessTokenEvents.dispatchEvent(new CustomEvent(ACCESS_TOKEN_CHANGE_EVENT, { detail: value }))
}

const clearAccessToken = () => {
  if (accessToken !== null) {
    authGeneration += 1
  }
  accessToken = null
  accessTokenEvents.dispatchEvent(new CustomEvent(ACCESS_TOKEN_CHANGE_EVENT, { detail: null }))
}

const onAccessTokenChange = (listener: (token: string | null) => void) => {
  const handler = (event: Event) => listener((event as CustomEvent<string | null>).detail)
  accessTokenEvents.addEventListener(ACCESS_TOKEN_CHANGE_EVENT, handler)
  return () => accessTokenEvents.removeEventListener(ACCESS_TOKEN_CHANGE_EVENT, handler)
}

const assertSameTabSession = (token: string) => {
  let expected = tabSessionId
  try {
    expected ??= sessionStorage.getItem(TAB_SESSION_KEY) ?? undefined
  } catch {
    // 当前页面内已有会话时继续使用内存中的标识。
  }
  if (expected && expected !== getSessionId(token)) throw new SessionChangedError()
}

export {
  isLogin,
  getAccessToken,
  getAuthGeneration,
  getSessionId,
  assertSameTabSession,
  SessionChangedError,
  setAccessToken,
  clearAccessToken,
  onAccessTokenChange,
}
