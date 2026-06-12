<script setup>
import { computed, ref, watch } from 'vue'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  steps: {
    type: Array,
    default: () => [],
  },
  streaming: {
    type: Boolean,
    default: false,
  },
})

const expandedMap = ref({})

const visibleSteps = computed(() =>
  (props.steps || []).filter((step) => step?.content || step?.status === 'running'),
)

function stepKey(step, index) {
  return `${step.type}-${index}`
}

function stepLabel(step) {
  if (step.type === 'reasoning') return '深度思考'
  if (step.type === 'tool') return step.name || '工具调用'
  return step.title || '处理过程'
}

function stepStatusText(step) {
  if (step.status === 'running') return '进行中'
  if (step.status === 'error') return '失败'
  return '已完成'
}

function isExpanded(step, index) {
  const key = stepKey(step, index)
  if (expandedMap.value[key] != null) {
    return expandedMap.value[key]
  }
  return step.status === 'running'
}

function toggle(step, index) {
  const key = stepKey(step, index)
  expandedMap.value[key] = !isExpanded(step, index)
}

watch(
  () => props.steps,
  (steps) => {
    steps?.forEach((step, index) => {
      const key = stepKey(step, index)
      if (step.status === 'running' && expandedMap.value[key] == null) {
        expandedMap.value[key] = true
      }
    })
  },
  { deep: true },
)
</script>

<template>
  <div v-if="visibleSteps.length > 0" class="chat-process-trace">
    <div
        v-for="(step, index) in visibleSteps"
        :key="stepKey(step, index)"
        class="chat-process-step"
        :class="[`is-${step.type}`, { 'is-running': step.status === 'running' }]"
    >
      <button
          type="button"
          class="chat-process-step-header"
          @click="toggle(step, index)"
      >
        <TheIcon
            :icon="step.type === 'tool' ? 'hugeicons:wrench-01' : 'hugeicons:brain-02'"
            :size="14"
            color="var(--primary-color)"
        />
        <span class="chat-process-step-title">{{ stepLabel(step) }}</span>
        <span class="chat-process-step-status">{{ stepStatusText(step) }}</span>
        <TheIcon
            :icon="isExpanded(step, index)
              ? 'material-symbols:keyboard-arrow-up'
              : 'material-symbols:keyboard-arrow-down'"
            :size="16"
            color="var(--chat-muted-text)"
        />
      </button>
      <div v-show="isExpanded(step, index)" class="chat-process-step-body">
        <pre class="chat-process-step-content">{{ step.content }}</pre>
        <span
            v-if="step.status === 'running' && streaming"
            class="chat-process-step-cursor"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-process-trace {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
}

.chat-process-step {
  overflow: hidden;
  border: 1px solid var(--chat-input-border, #e8e8e8);
  border-radius: 10px;
  background: color-mix(in srgb, var(--chat-input-surface, #fff) 96%, var(--primary-color, #f4511e));
}

.chat-process-step.is-running {
  border-color: color-mix(in srgb, var(--primary-color, #f4511e) 35%, var(--chat-input-border, #e8e8e8));
}

.chat-process-step-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.chat-process-step-title {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--n-text-color, #333);
}

.chat-process-step-status {
  font-size: 11px;
  color: var(--chat-muted-text, #a3a3a3);
  white-space: nowrap;
}

.chat-process-step.is-running .chat-process-step-status {
  color: var(--primary-color, #f4511e);
}

.chat-process-step-body {
  padding: 0 10px 10px;
}

.chat-process-step-content {
  margin: 0;
  max-height: 240px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.6;
  color: var(--n-text-color-2, #666);
  font-family: inherit;
  scrollbar-width: thin;
  scrollbar-color: #ccc transparent;
}

.chat-process-step-content::-webkit-scrollbar {
  width: 5px;
}

.chat-process-step-content::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.chat-process-step-cursor {
  display: inline-block;
  width: 6px;
  height: 14px;
  margin-left: 2px;
  background: var(--primary-color, #f4511e);
  border-radius: 1px;
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
</style>
