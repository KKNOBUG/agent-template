import { request, getToken } from '@/utils'

const API_BASE = import.meta.env.VITE_BASE_API || '/api'

function parseErrorDetail(detail) {
  if (!detail) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join('; ')
  }
  return String(detail)
}

export default {
  // 认证接口复用 /base/auth/* 路径（后端 user 模块统一认证）
  login: (data) => request.post('/base/auth/access_token', data, { noNeedToken: true }),
  register: (data) => request.post('/user/create', data, { noNeedToken: true }),
  getUserInfo: () => request.post('/base/auth/userinfo'),
  logout: () => request.post('/user/logout'),

  fetchConversations: () => request.get('/conversations/'),
  fetchConversation: (id) => request.get(`/conversations/${id}`),
  deleteConversation: (id) => request.delete(`/conversations/${id}`),

  fetchKnowledgeBases: (search = '') =>
    request.get(search ? `/knowledge-bases/?search=${encodeURIComponent(search)}` : '/knowledge-bases/'),
  createKnowledgeBase: (data) => request.post('/knowledge-bases/', data),
  deleteKnowledgeBase: (id) => request.delete(`/knowledge-bases/${id}`),
  fetchDocuments: (kbId) => request.get(`/knowledge-bases/${kbId}/documents`),
  deleteDocument: (kbId, docId) => request.delete(`/knowledge-bases/${kbId}/documents/${docId}`),
  fetchChunks: (kbId, docId) => request.get(`/knowledge-bases/${kbId}/chunks?doc_id=${docId}`),

  fetchModelConfigs: () => request.get('/model-configs/'),
  createModelConfig: (data) => request.post('/model-configs/', data),
  updateModelConfig: (id, data) => request.put(`/model-configs/${id}`, data),
  deleteModelConfig: (id) => request.delete(`/model-configs/${id}`),
  setDefaultModelConfig: (id) => request.post(`/model-configs/${id}/default`),
}

export async function uploadDocument(kbId, file) {
  const token = getToken()
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/knowledge-bases/${kbId}/documents`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(parseErrorDetail(error.detail) || '上传失败')
  }

  return res.json()
}

export function chatStream(
  question,
  conversationId,
  kbIds = [],
  modelConfigId = null,
  { onToken, onMeta, onDone, onError }
) {
  const controller = new AbortController()
  const token = getToken()

  fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      kb_ids: kbIds,
      model_config_id: modelConfigId,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(parseErrorDetail(error.detail) || '请求失败')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let eventType = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            const dataStr = line.slice(5).trim()
            if (!dataStr) continue
            try {
              const data = JSON.parse(dataStr)
              if (eventType === 'token' && onToken) onToken(data.content)
              else if (eventType === 'meta' && onMeta) onMeta(data)
              else if (eventType === 'done' && onDone) onDone(data.content)
              else if (eventType === 'error' && onError) onError(new Error(data.message))
            } catch {
              // ignore parse errors
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError' && onError) onError(err)
    })

  return { abort: () => controller.abort() }
}
