<script setup>
defineOptions({ name: 'Chat' })

import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import { NButton, NLayout, NLayoutContent, NLayoutSider, NSkeleton } from 'naive-ui'
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
const isConversationLoading = ref(false)
const messagesContainer = ref(null)
const inputRef = ref(null)
const showScrollFab = ref(false)
const scrollFabToBottom = ref(true)
let currentConvId = null
let streamController = null
let loadConversationSeq = 0

function normalizeConversationId(id) {
  if (id == null || id === '') return null
  return String(Array.isArray(id) ? id[0] : id)
}

// 知识库和模型配置
const knowledgeBases = ref([])
const modelConfigs = ref([])
const selectedKBs = ref([])
const selectedModelConfig = ref('')

// 从URL获取对话ID
const conversationId = ref(normalizeConversationId(route.query.conversation))

async function loadConversations() {
  try {
    conversations.value = await api.fetchConversations()
  } catch (err) {
    console.error('[Chat] 加载对话列表失败:', err)
    conversations.value = []
  }
}

function buildConversationTitle(question) {
  if (!question) return '新对话'
  return question.slice(0, 20) + (question.length > 20 ? '...' : '')
}

function prependConversation(id, title) {
  const existingIdx = conversations.value.findIndex((c) => c.id === id)
  if (existingIdx >= 0) {
    const [conv] = conversations.value.splice(existingIdx, 1)
    conversations.value.unshift(conv)
    return
  }
  conversations.value.unshift({ id, title: title || '新对话' })
}

function bumpConversationToTop(id) {
  const idx = conversations.value.findIndex((c) => c.id === id)
  if (idx > 0) {
    const [conv] = conversations.value.splice(idx, 1)
    conversations.value.unshift(conv)
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
    await switchToConversation(conversationId.value)
  }

  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', onMessagesScroll, { passive: true })
  }
  updateScrollFabState()
})

onUnmounted(() => {
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', onMessagesScroll)
  }
})

watch(messages, () => {
  nextTick(updateScrollFabState)
})

async function switchToConversation(newId) {
  const targetId = normalizeConversationId(newId)

  if (streamController) {
    streamController.abort()
    streamController = null
  }
  isLoading.value = false
  conversationId.value = targetId

  if (targetId) {
    await loadConversation(targetId)
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
  updateScrollFabState()
}

// 仅处理浏览器前进/后退、新建对话等外部 URL 变化
watch(() => route.query.conversation, async (newId, oldId) => {
  if (normalizeConversationId(newId) === normalizeConversationId(oldId)) return

  const targetId = normalizeConversationId(newId)
  if (targetId === normalizeConversationId(currentConvId)) return

  await switchToConversation(targetId)
})

async function loadConversation(id) {
  const targetId = normalizeConversationId(id)
  const seq = ++loadConversationSeq

  isConversationLoading.value = true
  messages.value = []

  try {
    const detail = await api.fetchConversation(targetId)
    if (seq !== loadConversationSeq) return

    currentConvId = targetId
    messages.value = detail.messages.map(m => ({
      role: m.role,
      content: m.content,
      prompt_tokens: m.prompt_tokens,
      completion_tokens: m.completion_tokens,
      reasoning_tokens: m.reasoning_tokens,
    }))
    if (detail.knowledge_base_ids != null) {
      selectedKBs.value = detail.knowledge_base_ids
    }
    if (detail.model_config_id) {
      selectedModelConfig.value = detail.model_config_id
    }
  } catch (err) {
    if (seq !== loadConversationSeq) return
    console.error('[Chat] 加载对话失败:', err)
    messages.value = []
    window.$message?.error('加载对话失败')
  } finally {
    if (seq === loadConversationSeq) {
      isConversationLoading.value = false
    }
  }
}

async function selectConversation(id) {
  const targetId = normalizeConversationId(id)

  // 点击列表时直接加载，不依赖 router watch（避免 URL 已匹配或 currentConvId 误判导致跳过）
  await switchToConversation(targetId)

  if (normalizeConversationId(route.query.conversation) !== targetId) {
    await router.replace({ path: '/ai-manage/chat', query: { conversation: targetId } })
  }
}

async function startNewChat() {
  if (normalizeConversationId(route.query.conversation)) {
    await router.replace({ path: '/ai-manage/chat' })
  } else {
    await switchToConversation(null)
  }
}

async function handleDeleteConversation(id) {
  if (!confirm('确定要删除这个对话吗？')) return
  try {
    await api.deleteConversation(id)
    await loadConversations()
    if (normalizeConversationId(currentConvId) === normalizeConversationId(id)) {
      await startNewChat()
    }
  } catch (err) {
    window.$message?.error('删除失败: ' + err.message)
  }
}

const SCROLL_EDGE_THRESHOLD = 48

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function scrollToTop() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = 0
  }
}

function updateScrollFabState() {
  const el = messagesContainer.value
  if (!el || isConversationLoading.value || messages.value.length === 0) {
    showScrollFab.value = false
    return
  }

  const { scrollTop, scrollHeight, clientHeight } = el
  const maxScroll = scrollHeight - clientHeight
  if (maxScroll <= SCROLL_EDGE_THRESHOLD) {
    showScrollFab.value = false
    return
  }

  showScrollFab.value = true
  // 以可滚动区域中点为界：上半区显示「跳到底部」，下半区显示「返回顶部」
  scrollFabToBottom.value = scrollTop < maxScroll / 2
}

function onMessagesScroll() {
  updateScrollFabState()
}

function handleScrollFabClick() {
  if (scrollFabToBottom.value) {
    scrollToBottom()
  } else {
    scrollToTop()
  }
  nextTick(updateScrollFabState)
}

async function sendMessage() {
  const question = inputText.value.trim()

  if (!question || isLoading.value) {
    return
  }

  inputText.value = ''
  messages.value.push({ role: 'user', content: question })
  messages.value.push({ role: 'assistant', content: '' })
  isLoading.value = true

  await nextTick()
  scrollToBottom()

  const assistantIdx = messages.value.length - 1

  streamController = chatStream(
      question,
      currentConvId,
      selectedKBs.value,
      selectedModelConfig.value,
      {
        onMeta(data) {
          if (data.conversation_id && !currentConvId) {
            currentConvId = data.conversation_id
            conversationId.value = data.conversation_id
            // 更新URL，使刷新页面后能保持对话
            router.replace({ path: '/ai-manage/chat', query: { conversation: data.conversation_id } })
            const firstQuestion = messages.value.find((m) => m.role === 'user')?.content
            prependConversation(data.conversation_id, buildConversationTitle(firstQuestion))
          }
        },
        onToken(token) {
          messages.value[assistantIdx].content += token
          nextTick(scrollToBottom)
        },
        onDone(data) {
          if (data?.usage) {
            messages.value[assistantIdx].prompt_tokens = data.usage.prompt_tokens
            messages.value[assistantIdx].completion_tokens = data.usage.completion_tokens
            messages.value[assistantIdx].reasoning_tokens = data.usage.reasoning_tokens
          }
          isLoading.value = false
          streamController = null
          if (currentConvId) {
            bumpConversationToTop(currentConvId)
          }
        },
        onError() {
          messages.value[assistantIdx].content += '\n\n[连接中断，请重试]'
          isLoading.value = false
          streamController = null
        },
      }
  )
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
      <NButton secondary circle type="primary" block @click="startNewChat">
        <template #icon>
          <TheIcon icon="hugeicons:message-add-02" :size="16" />
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
          <span class="conv-icon">
            <TheIcon
                icon="hugeicons:message-02"
                :size="14"
                :color="conversationId === conv.id ? 'var(--primary-color)' : undefined"
            />
          </span>
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

    <NLayoutContent
        class="chat-main-content"
        content-style="height: 100%; overflow: hidden; background-color: var(--chat-surface);"
    >
      <CommonPage :show-header="false" :show-footer="false" inherit-background>
        <div class="chat-panel">
          <div class="chat-thread">
            <div
                ref="messagesContainer"
                class="messages-area"
                :class="{ 'is-empty': !isConversationLoading && messages.length === 0 }"
            >
              <div v-if="isConversationLoading" class="messages-skeleton">
                <div class="message-skeleton user">
                  <div class="avatar-col" />
                  <NSkeleton class="skeleton-bubble" :sharp="false" height="40px" width="38%" />
                  <div class="avatar-col">
                    <NSkeleton circle width="36px" height="36px" />
                  </div>
                </div>
                <div class="message-skeleton assistant">
                  <div class="avatar-col">
                    <NSkeleton circle width="36px" height="36px" />
                  </div>
                  <div class="skeleton-bubble skeleton-bubble--wide">
                    <NSkeleton text :repeat="3" />
                  </div>
                  <div class="avatar-col" />
                </div>
                <div class="message-skeleton user">
                  <div class="avatar-col" />
                  <NSkeleton class="skeleton-bubble" :sharp="false" height="40px" width="32%" />
                  <div class="avatar-col">
                    <NSkeleton circle width="36px" height="36px" />
                  </div>
                </div>
                <div class="message-skeleton assistant">
                  <div class="avatar-col">
                    <NSkeleton circle width="36px" height="36px" />
                  </div>
                  <div class="skeleton-bubble skeleton-bubble--wide">
                    <NSkeleton text :repeat="2" />
                  </div>
                  <div class="avatar-col" />
                </div>
              </div>

              <div v-else-if="messages.length === 0" class="welcome">
                <div class="welcome-brand">
                  <icon-custom-logo-new text-36 color-primary flex-shrink-0 />
                  <p class="welcome-greeting">
                    我是
                    <span class="welcome-app-name">{{ $t('app_name') }}</span>
                    智能助手，很高兴见到你！
                  </p>
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
                    :prompt-tokens="msg.prompt_tokens"
                    :completion-tokens="msg.completion_tokens"
                    :reasoning-tokens="msg.reasoning_tokens"
                />
              </template>
            </div>

            <div class="input-area">
              <button
                  v-show="showScrollFab"
                  type="button"
                  class="scroll-fab"
                  :title="scrollFabToBottom ? '跳到底部' : '返回顶部'"
                  @click="handleScrollFabClick"
              >
                <TheIcon
                    :icon="scrollFabToBottom ? 'material-symbols:keyboard-arrow-down' : 'material-symbols:keyboard-arrow-up'"
                    :size="18"
                    color="var(--primary-color)"
                />
              </button>
              <div class="input-grid">
                <div class="input-box">
                  <textarea
                      ref="inputRef"
                      v-model="inputText"
                      class="input-textarea"
                      placeholder="请输入您的问题... Enter发送消息 / Shift+Enter换行"
                      rows="3"
                      :disabled="isLoading || isConversationLoading"
                      @keydown="handleKeydown"
                  />
                  <button
                      class="send-btn"
                      type="button"
                      :disabled="!inputText.trim() || isLoading || isConversationLoading"
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
  border-radius: 4px;
  cursor: pointer;
  transition: color 0.2s;
  margin-bottom: 2px;
  color: var(--n-text-color);
  font-size: 12px;
}

.conv-icon {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  color: var(--n-text-color-3);
  transition: color 0.2s;
}

.conversation-item:hover:not(.active) {
  color: var(--n-text-color);
}

.conversation-item:hover:not(.active) .conv-icon {
  color: var(--n-text-color-2);
}

.conversation-item.active {
  background: transparent;
  color: var(--primary-color, #f4511e);
}

.conversation-item.active .conv-icon {
  color: var(--primary-color, #f4511e);
}

.conversation-item.active .conv-icon :deep(.n-icon),
.conversation-item.active .conv-icon :deep(svg) {
  color: var(--primary-color, #f4511e);
}

.conversation-item.active .conv-title {
  color: var(--primary-color, #f4511e);
}

.conv-icon :deep(.n-icon),
.conv-icon :deep(svg) {
  color: currentColor;
}

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  transition: color 0.2s;
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

.delete-btn svg {
  width: 14px;
  height: 14px;
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
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-thread {
  --avatar-size: 36px;
  --avatar-gap: 12px;
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 24px;
}

.messages-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  /* 滚动条样式 */
  scrollbar-width: thin; /* 火狐：细滚动条 */
  scrollbar-color: #ccc transparent;
}

/* Chrome / Edge / Safari */
.messages-area::-webkit-scrollbar {
  width: 6px;
}
.messages-area::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}
.messages-area::-webkit-scrollbar-track {
  background: transparent;
}

.messages-area.is-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.messages-skeleton {
  padding: 8px 0;
}

.message-skeleton {
  display: grid;
  grid-template-columns: var(--avatar-size, 36px) 1fr var(--avatar-size, 36px);
  gap: var(--avatar-gap, 12px);
  align-items: start;
  margin: 0 auto 16px;
  width: 90%;
}

.message-skeleton .avatar-col {
  width: 36px;
  flex-shrink: 0;
}

.skeleton-bubble {
  min-width: 0;
}

.skeleton-bubble--wide {
  width: 100%;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  box-sizing: border-box;
}

.welcome-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 640px;
}

.welcome-greeting {
  font-size: 18px;
  font-weight: 500;
  line-height: 1.5;
  color: var(--n-text-color, #333);
}

.welcome-app-name {
  margin: 0 4px;
  font-weight: 700;
  color: var(--primary-color, #f4511e);
}

.input-area {
  position: relative;
  flex-shrink: 0;
  margin-top: auto;
  padding: 14px 0 1px;
}

.scroll-fab {
  position: absolute;
  left: 50%;
  top: -5px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--chat-input-border);
  border-radius: 50%;
  background-color: var(--chat-input-surface);
  box-shadow: var(--chat-input-shadow);
  cursor: pointer;
  transform: translate(-50%, -50%);
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.scroll-fab:hover {
  border-color: var(--primary-color, #f4511e);
}

.scroll-fab:active {
  transform: translate(-50%, -50%) scale(0.96);
}

.input-grid {
  display: grid;
  grid-template-columns: var(--avatar-size) 0.99fr var(--avatar-size);
  gap: var(--avatar-gap);
  align-items: end;
  margin: 0 auto;
  width: 90%;
}

.input-box {
  grid-column: 2;
  min-width: 0;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 12px 10px 16px;
  border: 1px solid var(--chat-input-border);
  border-radius: 12px;
  background-color: var(--chat-input-surface);
  box-shadow: var(--chat-input-shadow);
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
  color: var(--chat-muted-text);
  font-size: 12px;
  opacity: 1;
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
  color: var(--chat-muted-text);
  line-height: 1;
}
</style>
