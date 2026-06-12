<script setup>
import { computed, ref } from 'vue'
import { NPopover, NSwitch } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])

const showPopover = ref(false)

const triggerTitle = computed(() =>
  props.modelValue ? '深度思考：已开启' : '深度思考：已关闭',
)

function handleSwitchChange(value) {
  emit('update:modelValue', value)
}
</script>

<template>
  <NPopover
      v-model:show="showPopover"
      trigger="click"
      placement="top-start"
      :show-arrow="true"
      raw
  >
    <template #trigger>
      <button
          type="button"
          class="chat-thinking-trigger"
          :class="{ 'is-active': modelValue }"
          :title="triggerTitle"
      >
        <TheIcon icon="hugeicons:brain-02" :size="18" color="#fff" />
      </button>
    </template>

    <div class="chat-thinking-panel">
      <div class="chat-thinking-header">
        <span class="chat-thinking-title">深度思考</span>
        <NSwitch
            :value="modelValue"
            size="small"
            @update:value="handleSwitchChange"
        />
      </div>
      <p class="chat-thinking-desc">
        开启后模型将先进行链式推理再输出答案，适合复杂问题，但会消耗更多 Token、响应更慢。
      </p>
    </div>
  </NPopover>
</template>

<style scoped>
.chat-thinking-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: var(--primary-color, #f4511e);
  color: #fff;
  opacity: 0.4;
  flex-shrink: 0;
  cursor: pointer;
  transition: background-color 0.2s, opacity 0.2s;
}

.chat-thinking-trigger.is-active {
  opacity: 1;
}

.chat-thinking-trigger.is-active:hover {
  background: var(--primary-color-hover, #f76b3c);
}

.chat-thinking-trigger :deep(.n-icon) {
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-thinking-panel {
  width: 260px;
  padding: 10px;
  border-radius: 10px;
  background: var(--chat-input-surface, #fff);
  border: 1px solid var(--chat-input-border, #e8e8e8);
  box-shadow: var(--chat-input-shadow, 0 8px 24px rgba(0, 0, 0, 0.12));
}

.chat-thinking-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chat-thinking-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--n-text-color, #333);
}

.chat-thinking-desc {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--chat-muted-text, #a3a3a3);
}
</style>
