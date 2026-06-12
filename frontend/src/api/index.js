import { request, getToken } from '@/utils'
import { handleUnauthorized, isUnauthorizedCode } from '@/utils/http/auth'

const API_BASE = import.meta.env.VITE_BASE_API || '/api'

function payload(res) {
  return res?.data ?? res
}

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

  fetchConversations: () => request.get('/conversations/').then(payload),
  fetchConversation: (id) => request.get(`/conversations/${id}`).then(payload),
  deleteConversation: (id) => request.delete(`/conversations/${id}`).then(payload),

  fetchKnowledgeBases: (search = '') =>
      request
          .get(search ? `/knowledge-bases/?search=${encodeURIComponent(search)}` : '/knowledge-bases/')
          .then(payload),
  createKnowledgeBase: (data) => request.post('/knowledge-bases/', data).then(payload),
  updateKnowledgeBase: (id, data) => request.put(`/knowledge-bases/${id}`, data).then(payload),
  deleteKnowledgeBase: (id) => request.delete(`/knowledge-bases/${id}`).then(payload),
  fetchDocuments: (kbId) => request.get(`/knowledge-bases/${kbId}/documents`).then(payload),
  retryDocument: (kbId, docId) => request.post(`/knowledge-bases/${kbId}/documents/${docId}/retry`).then(payload),
  deleteDocument: (kbId, docId) => request.delete(`/knowledge-bases/${kbId}/documents/${docId}`).then(payload),
  fetchChunks: (kbId, docId) =>
      request.get(`/knowledge-bases/${kbId}/chunks?document_id=${docId}`).then(payload),

  fetchModelConfigs: () => request.get('/model-configs/').then(payload),
  createModelConfig: (data) => request.post('/model-configs/', data).then(payload),
  updateModelConfig: (id, data) => request.put(`/model-configs/${id}`, data).then(payload),
  deleteModelConfig: (id) => request.delete(`/model-configs/${id}`).then(payload),
  setDefaultModelConfig: (id) => request.post(`/model-configs/${id}/default`).then(payload),
}

export async function uploadDocument(kbId, file) {
  const token = getToken()
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/knowledge-bases/${kbId}/documents`, {
    method: 'POST',
    headers: token ? { token } : {},
    body: formData,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.message || parseErrorDetail(error.detail) || '上传失败')
  }

  const body = await res.json()
  if (isUnauthorizedCode(body?.code)) {
    await handleUnauthorized()
    throw new Error(body?.message || '登录已过期')
  }
  if (body?.code !== '000000' || body?.status !== 'success') {
    throw new Error(body?.message || '上传失败')
  }
  return body.data ?? body
}

export function chatStream(
    question,
    conversationId,
    knowledgeBaseIds = [],
    modelConfigId = null,
    { onToken, onMeta, onDone, onError }
) {
  const controller = new AbortController()
  const token = getToken()

  fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      token,
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      knowledge_base_ids: knowledgeBaseIds,
      model_config_id: modelConfigId,
    }),
    signal: controller.signal,
  })
      .then(async (response) => {
        const contentType = response.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          const body = await response.json().catch(() => ({}))
          if (isUnauthorizedCode(body?.code)) {
            await handleUnauthorized()
            throw new Error(body?.message || '登录已过期')
          }
          throw new Error(body?.message || parseErrorDetail(body.detail) || '请求失败')
        }

        if (!response.ok) {
          const error = await response.json().catch(() => ({}))
          if (isUnauthorizedCode(error?.code)) {
            await handleUnauthorized()
          }
          throw new Error(parseErrorDetail(error.detail) || error.message || '请求失败')
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
                else if (eventType === 'done' && onDone) onDone(data)
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
