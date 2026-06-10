<script setup>
defineOptions({ name: 'Chat' })

import { ref, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import { NButton, NLayout, NLayoutContent, NLayoutSider } from 'naive-ui'
import MessageBubble from '../../components/MessageBubble.vue'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api, { chatStream } from '@/api'

const route = useRoute()
const router = useRouter()

const conversations = ref([])

const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const messagesContainer = ref(null)
const inputRef = ref(null)
let currentConvId = null
let streamController = null

// 知识库和模型配置
const knowledgeBases = ref([])
const modelConfigs = ref([])
const selectedKBs = ref([])
const selectedModelConfig = ref('')

// 从URL获取对话ID
const conversationId = ref(route.query.conversation || null)

async function loadConversations() {
  try {
    conversations.value = await api.fetchConversations()
  } catch (err) {
    console.error('[Chat] 加载对话列表失败:', err)
    conversations.value = []
  }
}

onMounted(async () => {
  await loadConversations()

  // 加载知识库和模型配置（后台默认，不在界面展示）
  try {
    const kbs = await api.fetchKnowledgeBases()
    knowledgeBases.value = kbs || []
    console.log('[Chat] 知识库加载完成:', kbs)
    // 自动选择第一个知识库
    if (kbs && kbs.length > 0) {
      selectedKBs.value = [kbs[0].id]
      console.log('[Chat] 自动选择知识库:', kbs[0].id)
    }
  } catch (err) {
    console.error('[Chat] 加载知识库失败:', err)
    knowledgeBases.value = []
  }

  try {
    const configs = await api.fetchModelConfigs()
    modelConfigs.value = configs || []
    console.log('[Chat] 模型配置加载完成:', configs)
    if (modelConfigs.value.length > 0) {
      selectedModelConfig.value = modelConfigs.value.find(c => c.is_default)?.id || modelConfigs.value[0].id
      console.log('[Chat] 默认模型配置ID:', selectedModelConfig.value)
    }
  } catch (err) {
    console.error('[Chat] 加载模型配置失败:', err)
    modelConfigs.value = []
  }

  if (inputRef.value) inputRef.value.focus()

  // 加载对话
  if (conversationId.value) {
    await loadConversation(conversationId.value)
  }
})

// 监听URL变化
watch(() => route.query.conversation, async (newId) => {
  conversationId.value = newId
  if (streamController) {
    streamController.abort()
    streamController = null
  }
  isLoading.value = false

  if (newId) {
    await loadConversation(newId)
  } else {
    currentConvId = null
    messages.value = []
    // 新建对话时，恢复默认知识库选择
    if (knowledgeBases.value.length > 0) {
      selectedKBs.value = [knowledgeBases.value[0].id]
      console.log('[Chat] 新建对话，自动选择知识库:', knowledgeBases.value[0].id)
    } else {
      selectedKBs.value = []
    }
    // 恢复默认模型配置
    if (modelConfigs.value.length > 0) {
      selectedModelConfig.value = modelConfigs.value.find(c => c.is_default)?.id || modelConfigs.value[0].id
      console.log('[Chat] 新建对话，使用默认模型配置:', selectedModelConfig.value)
    }
  }
  await nextTick()
  scrollToBottom()
})

async function loadConversation(id) {
  currentConvId = id
  const detail = await api.fetchConversation(id)
  messages.value = detail.messages.map(m => ({
    role: m.role,
    content: m.content,
  }))
  // 恢复知识库和模型配置选择
  if (detail.kb_ids) {
    selectedKBs.value = detail.kb_ids
  }
  if (detail.model_config_id) {
    selectedModelConfig.value = detail.model_config_id
  }
}

function selectConversation(id) {
  router.push({ path: '/ai-manage/chat', query: { conversation: id } })
}

function startNewChat() {
  currentConvId = null
  messages.value = []
  conversationId.value = null
  router.push('/ai-manage/chat')
}

async function handleDeleteConversation(id) {
  if (!confirm('确定要删除这个对话吗？')) return
  try {
    await api.deleteConversation(id)
    await loadConversations()
    if (currentConvId === id) {
      startNewChat()
    }
  } catch (err) {
    window.$message?.error('删除失败: ' + err.message)
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

async function sendMessage(questionOverride = null) {
  // 确保 questionOverride 是字符串（防止传入事件对象）
  const overrideStr = typeof questionOverride === 'string' ? questionOverride : null
  const question = (overrideStr || inputText.value).trim()

  console.log('[Chat.sendMessage] 开始执行')
  console.log('[Chat.sendMessage] questionOverride:', questionOverride)
  console.log('[Chat.sendMessage] overrideStr:', overrideStr)
  console.log('[Chat.sendMessage] inputText.value:', inputText.value)
  console.log('[Chat.sendMessage] 最终 question:', question)
  console.log('[Chat.sendMessage] isLoading:', isLoading.value)

  if (!question || isLoading.value) {
    console.log('[Chat.sendMessage] 退出：question为空或isLoading为true')
    return
  }

  console.log('[Chat.sendMessage] 清空输入框')
  inputText.value = ''

  console.log('[Chat.sendMessage] 添加用户消息')
  messages.value.push({ role: 'user', content: question })
  messages.value.push({ role: 'assistant', content: '' })
  isLoading.value = true

  await nextTick()
  scrollToBottom()

  const assistantIdx = messages.value.length - 1

  console.log('[Chat.sendMessage] 调用 chatStream')
  console.log('[Chat.sendMessage] 参数 - question:', question)
  console.log('[Chat.sendMessage] 参数 - currentConvId:', currentConvId)
  console.log('[Chat.sendMessage] 参数 - selectedKBs:', selectedKBs.value)
  console.log('[Chat.sendMessage] 参数 - selectedModelConfig:', selectedModelConfig.value)

  streamController = chatStream(
      question,
      currentConvId,
      selectedKBs.value,
      selectedModelConfig.value,
      {
        onMeta(data) {
          console.log('[Chat.sendMessage] onMeta 回调:', data)
          if (data.conversation_id && !currentConvId) {
            currentConvId = data.conversation_id
            // 更新URL，使刷新页面后能保持对话
            router.replace({ path: '/ai-manage/chat', query: { conversation: data.conversation_id } })
            loadConversations()
          }
        },
        onToken(token) {
          messages.value[assistantIdx].content += token
          nextTick(scrollToBottom)
        },
        onDone() {
          console.log('[Chat.sendMessage] onDone 回调')
          isLoading.value = false
          streamController = null
          loadConversations()
        },
        onError(err) {
          console.error('[Chat.sendMessage] onError 回调:', err)
          messages.value[assistantIdx].content += '\n\n[连接中断，请重试]'
          isLoading.value = false
          streamController = null
        },
      }
  )

  console.log('[Chat.sendMessage] chatStream 调用完成')
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text, { breaks: true })
}

function handleQuickQuestion(question) {
  console.log('[Chat] 快速问题被点击:', question)
  console.log('[Chat] 问题类型:', typeof question)
  console.log('[Chat] 当前 isLoading:', isLoading.value)
  console.log('[Chat] 当前 currentConvId:', currentConvId)
  console.log('[Chat] 当前 selectedKBs:', selectedKBs.value)
  console.log('[Chat] 当前 selectedModelConfig:', selectedModelConfig.value)

  // 确保 question 是字符串
  if (typeof question !== 'string') {
    console.error('[Chat] 错误：question 不是字符串', question)
    return
  }

  // 检查知识库是否已选择
  if (!selectedKBs.value || selectedKBs.value.length === 0) {
    console.warn('[Chat] 警告：未选择知识库，将使用默认检索')
    // 如果有可用知识库，自动选择第一个
    if (knowledgeBases.value.length > 0) {
      selectedKBs.value = [knowledgeBases.value[0].id]
      console.log('[Chat] 自动选择知识库:', selectedKBs.value[0])
    } else {
      console.error('[Chat] 错误：没有可用的知识库')
      alert('请先创建或选择知识库')
      return
    }
  }

  // 检查模型配置
  if (!selectedModelConfig.value) {
    console.warn('[Chat] 警告：未选择模型配置，使用默认')
    if (modelConfigs.value.length > 0) {
      selectedModelConfig.value = modelConfigs.value.find(c => c.is_default)?.id || modelConfigs.value[0].id
      console.log('[Chat] 使用默认模型配置:', selectedModelConfig.value)
    }
  }

  // 直接调用 sendMessage，传入问题字符串
  sendMessage(question)
}
</script>

<template>
  <NLayout has-sider wh-full class="chat-page-layout">
    <NLayoutSider
        bordered
        :width="260"
        :collapsed-width="0"
        show-trigger="arrow-circle"
        :native-scrollbar="false"
        content-style="display: flex; flex-direction: column; height: 100%; padding: 12px; box-sizing: border-box;"
    >
      <NButton secondary type="primary" block @click="startNewChat">
        <template #icon>
          <TheIcon icon="material-symbols:add" :size="16" />
        </template>
        新建对话
      </NButton>

      <div class="conversation-list cus-scroll-y">
        <div
            v-for="conv in conversations"
            :key="conv.id"
            class="conversation-item"
            :class="{ active: conversationId === conv.id }"
            @click="selectConversation(conv.id)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
          <span class="conv-title">{{ conv.title || '新对话' }}</span>
          <button
              class="delete-btn"
              title="删除对话"
              @click.stop="handleDeleteConversation(conv.id)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
        <div v-if="conversations.length === 0" class="empty-conversations">
          暂无历史对话
        </div>
      </div>

      <p class="conversation-count">共 {{ conversations.length }} 个对话</p>
    </NLayoutSider>

    <NLayoutContent content-style="height: 100%; overflow: hidden;">
      <CommonPage :show-header="false" :show-footer="false">
        <div class="chat-panel">
          <div class="chat-thread">
            <div ref="messagesContainer" class="messages-area cus-scroll-y">
              <div v-if="messages.length === 0" class="welcome">
                <div class="welcome-icon">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--primary-color, #f4511e)" stroke-width="1.5">
                    <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h2>你好，有什么可以帮你的？</h2>
                <p>我是企业知识库智能助手，可以回答关于公司制度、技术文档、产品信息等问题。</p>
                <div class="quick-questions">
                  <button
                      v-for="q in [
                      '公司的考勤制度是什么？',
                      '产品的核心功能有哪些？',
                      '技术栈使用什么框架？',
                    ]"
                      :key="q"
                      class="quick-btn"
                      @click="handleQuickQuestion(q)"
                  >
                    {{ q }}
                  </button>
                </div>
              </div>

              <template v-else>
                <MessageBubble
                    v-for="(msg, idx) in messages"
                    :key="idx"
                    :role="msg.role"
                    :content="msg.content"
                    :html="msg.role === 'assistant' ? renderMarkdown(msg.content) : ''"
                    :isStreaming="isLoading && idx === messages.length - 1 && msg.role === 'assistant'"
                />
              </template>
            </div>

            <div class="input-area">
              <div class="input-grid">
                <div class="input-box">
                  <textarea
                      ref="inputRef"
                      v-model="inputText"
                      class="input-textarea"
                      placeholder="请输入您的问题... Enter发送消息 / Shift+Enter换行"
                      rows="3"
                      :disabled="isLoading"
                      @keydown="handleKeydown"
                  />
                  <button
                      class="send-btn"
                      type="button"
                      :disabled="!inputText.trim() || isLoading"
                      @click="sendMessage()"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                    </svg>
                  </button>
                </div>
                <p class="input-disclaimer">内容由 AI 生成，请仔细甄别 · KEENROBOT助手</p>
              </div>
            </div>
          </div>
        </div>
      </CommonPage>
    </NLayoutContent>
  </NLayout>
</template>

<style scoped>
.chat-page-layout {
  height: 100%;
  overflow: hidden;
}

.chat-page-layout :deep(section.cus-scroll-y) {
  overflow: hidden;
}

.conversation-list {
  flex: 1;
  margin-top: 12px;
  min-height: 0;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 2px;
  color: var(--n-text-color);
  font-size: 12px;
}

.conversation-item svg {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  color: var(--n-text-color-3);
}

.conversation-item:hover {
  background: var(--n-item-color-hover);
}

.conversation-item.active {
  background: rgba(244, 81, 30, 0.1);
  color: var(--primary-color, #f4511e);
}

.conversation-item.active svg {
  color: var(--primary-color, #f4511e);
}

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.empty-conversations {
  text-align: center;
  padding: 40px 12px;
  color: var(--n-text-color-3, #999);
  font-size: 12px;
}

.conversation-count {
  flex-shrink: 0;
  margin: 8px 0 0;
  padding-top: 8px;
  text-align: center;
  font-size: 11px;
  color: var(--n-text-color-3, #999);
  border-top: 1px solid var(--n-border-color);
}

.delete-btn {
  opacity: 0;
  background: none;
  border: none;
  color: var(--n-text-color-3, #999);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.conversation-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(208, 48, 80, 0.1);
  color: var(--error-color, #d03050);
}

.chat-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-thread {
  --avatar-size: 36px;
  --avatar-gap: 12px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 24px;
}

.messages-area {
  flex: 1;
  padding: 16px 0;
  min-height: 0;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 100%;
  padding: 40px 20px;
  gap: 12px;
  box-sizing: border-box;
}

.welcome-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(244, 81, 30, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}

.welcome h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--n-text-color);
}

.welcome p {
  color: var(--n-text-color-3, #999);
  max-width: 420px;
  font-size: 14px;
  line-height: 1.6;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 20px;
}

.quick-btn {
  padding: 8px 16px;
  border: 1px solid var(--n-border-color);
  border-radius: 20px;
  font-size: 13px;
  color: var(--n-text-color-3);
  background: transparent;
  transition: all 0.2s;
  cursor: pointer;
}

.quick-btn:hover {
  border-color: var(--primary-color-hover, #f76b3c);
  color: var(--primary-color, #f4511e);
  background: rgba(244, 81, 30, 0.06);
}

.input-area {
  flex-shrink: 0;
  padding: 0 0 8px;
}

.input-grid {
  display: grid;
  grid-template-columns: var(--avatar-size) 0.99fr var(--avatar-size);
  gap: var(--avatar-gap);
  align-items: end;
  margin: auto;
  width: 90%;
}

.input-box {
  grid-column: 2;
  min-width: 0;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 12px 10px 16px;
  border: 1px solid var(--n-border-color);
  border-radius: 12px;
  background: var(--n-color, #fff);
  box-shadow: 0 0 15px rgba(214, 214, 214, 0.2);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-box:focus-within {
  border-color: var(--primary-color-hover, #f4511e);
  box-shadow: 0 4px 20px rgba(244, 81, 30, 0.15);
}

.input-textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  resize: none;
  min-height: 24px;
  max-height: 120px;
  line-height: 24px;
  padding: 0;
  font-size: 14px;
  color: var(--n-text-color);
  box-sizing: border-box;
}

.input-textarea::placeholder {
  color: rgba(0, 0, 0, 0.28);
  font-size: 13px;
}

.input-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--primary-color, #f4511e);
  color: #fff;
  flex-shrink: 0;
  transition: all 0.2s;
  border: none;
  cursor: pointer;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-color-hover, #f76b3c);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.input-disclaimer {
  grid-column: 2;
  text-align: center;
  font-size: 10px;
  color: rgba(0, 0, 0, 0.28);
  line-height: 1;
}

:global(html.dark) .input-box {
  background: #2a2a2e;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}

:global(html.dark) .input-textarea::placeholder {
  color: rgba(255, 255, 255, 0.28);
}
</style>
