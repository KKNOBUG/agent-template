<script setup>
import ChatProcessTrace from './chat/ChatProcessTrace.vue'

defineProps({
  role: String,
  content: String,
  html: String,
  processTrace: {
    type: Array,
    default: () => [],
  },
  isStreaming: Boolean,
  promptTokens: Number,
  completionTokens: Number,
  reasoningTokens: Number,
})

function hasTokenUsage(promptTokens, completionTokens, reasoningTokens) {
  return (
      promptTokens != null
      || completionTokens != null
      || (reasoningTokens != null && reasoningTokens > 0)
  )
}
</script>

<template>
  <div class="message" :class="role">
    <div class="avatar-col">
      <div v-if="role === 'assistant'" class="avatar avatar--assistant">
        <icon-custom-logo-new text-36 color-primary />
      </div>
    </div>
    <div class="bubble">
      <ChatProcessTrace
          v-if="role === 'assistant' && processTrace.length > 0"
          :steps="processTrace"
          :streaming="isStreaming"
      />
      <div
          v-if="role === 'assistant' && (content || !processTrace.length)"
          class="markdown-body bubble-content"
          v-html="html"
      />
      <div v-else-if="role !== 'assistant'" class="text-content bubble-content">{{ content }}</div>
      <span v-if="isStreaming && content" class="cursor-blink"></span>
      <div
          v-if="role === 'assistant' && hasTokenUsage(promptTokens, completionTokens, reasoningTokens)"
          class="token-usage"
      >
        <span v-if="promptTokens != null" class="token-badge token-badge--prompt">
          <svg class="token-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 19V5M12 5l-6 6M12 5l6 6" />
          </svg>
          {{ promptTokens }}
        </span>
        <span v-if="completionTokens != null" class="token-badge token-badge--completion">
          <svg class="token-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 5v14M12 19l-6-6M12 19l6-6" />
          </svg>
          {{ completionTokens }}
        </span>
        <span v-if="reasoningTokens != null && reasoningTokens > 0" class="token-badge token-badge--reasoning">
          <svg class="token-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          {{ reasoningTokens }}
        </span>
      </div>
    </div>
    <div class="avatar-col">
      <div v-if="role === 'user'" class="avatar avatar--user">
        <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
        >
          <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: grid;
  grid-template-columns: 36px 1fr 36px;
  gap: 12px;
  align-items: start;
  margin: 0 auto 16px;
  width: 90%;
}

.avatar-col {
  width: 36px;
  flex-shrink: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar--assistant {
  background: none;
  border-radius: 0;
}

.avatar--user {
  border-radius: 30%;
  background: var(--chat-input-border);
}

.bubble {
  min-width: 0;
}

.bubble-content {
  box-sizing: border-box;
  min-height: 36px;
  padding: 8px 14px;
  line-height: 20px;
  word-break: break-word;
  font-size: 14px;
  border-radius: 12px;
}

.message.user .bubble-content {
  background-color: var(--chat-input-border);
}

.message.assistant .bubble-content {
  background: rgba(244, 81, 30, 0.1);
}

.message.assistant .bubble-content :deep(p) {
  margin: 0.4em 0;
}

.message.assistant .bubble-content :deep(p:first-child) {
  margin-top: 0;
}

.message.assistant .bubble-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message.assistant .bubble-content :deep(p:only-child) {
  margin: 0;
  line-height: 20px;
}

.token-usage {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
  padding-left: 2px;
}

.token-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  line-height: 16px;
}

.token-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.token-badge--prompt {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
}

.token-badge--completion {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}

.token-badge--reasoning {
  background: rgba(250, 140, 22, 0.12);
  color: #fa8c16;
}

.cursor-blink {
  display: inline-block;
  width: 7px;
  height: 16px;
  background: var(--primary-color, #f4511e);
  border-radius: 2px;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

:global(html.dark) .message.assistant .bubble-content {
  background: rgba(244, 81, 30, 0.12);
  color: #e2e8f0;
  border-color: rgba(244, 81, 30, 0.2);
}

:global(html.dark) .token-badge--prompt {
  background: rgba(24, 144, 255, 0.18);
}

:global(html.dark) .token-badge--completion {
  background: rgba(82, 196, 26, 0.18);
}

:global(html.dark) .token-badge--reasoning {
  background: rgba(250, 140, 22, 0.18);
}
</style>
