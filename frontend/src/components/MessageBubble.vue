<script setup>
defineProps({
  role: String,
  content: String,
  html: String,
  isStreaming: Boolean,
})
</script>

<template>
  <div class="message" :class="role">
    <div class="avatar-col">
      <div v-if="role === 'assistant'" class="avatar">
        <icon-custom-logo-new class="logo-icon" />
      </div>
    </div>
    <div class="bubble">
      <div v-if="role === 'assistant'" class="markdown-body bubble-content" v-html="html"></div>
      <div v-else class="text-content bubble-content">{{ content }}</div>
      <span v-if="isStreaming" class="cursor-blink"></span>
    </div>
    <div class="avatar-col">
      <div v-if="role === 'user'" class="avatar">
        <svg
            width="20"
            height="20"
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
  margin: 0 auto 16px; /* 关键：左右自动居中，底部保留 16px 间距 */
  width: 90%;
}

.avatar-col {
  width: 36px;
  flex-shrink: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .avatar {
  background: #e8e8e8;
  color: #64748b;
}

.message.assistant .avatar {
  background: rgba(244, 81, 30, 0.08);
}

.logo-icon {
  font-size: 28px;
  color: var(--primary-color, #f4511e);
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
  background-color: rgba(214, 214, 214, 0.28);
  border: 1px solid rgba(214, 214, 214, 0.32);
  border-radius: 12px 12px 12px 12px;
}

.message.assistant .bubble-content {
  background: rgba(244, 81, 30, 0.05);
  border: 1px solid rgba(244, 81, 30, 0.15);
  border-radius: 12px 12px 12px 12px;
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
</style>
