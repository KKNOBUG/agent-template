<script setup>
import { computed, ref, watch } from 'vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import {
  STEP_STATUS,
  STEP_TYPES,
  formatJsonBlock,
  isStepVisible,
  stepIcon,
  stepLabel,
} from '@/types/processStep'

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
    (props.steps || []).filter(isStepVisible),
)

function stepKey(step, index) {
  return `${step.type}-${index}`
}

function stepStatusText(step) {
  if (step.status === STEP_STATUS.RUNNING) return '进行中'
  if (step.status === STEP_STATUS.ERROR) return '失败'
  return '已完成'
}

function isExpanded(step, index) {
  const key = stepKey(step, index)
  if (expandedMap.value[key] != null) {
    return expandedMap.value[key]
  }
  return step.status === STEP_STATUS.RUNNING
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
        if (step.status === STEP_STATUS.RUNNING && expandedMap.value[key] == null) {
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
        :class="[`is-${step.type}`, { 'is-running': step.status === STEP_STATUS.RUNNING }]"
    >
      <button
          type="button"
          class="chat-process-step-header"
          @click="toggle(step, index)"
      >
        <TheIcon
            :icon="stepIcon(step)"
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
        <!-- reasoning -->
        <template v-if="step.type === STEP_TYPES.REASONING">
          <pre class="chat-process-step-content">{{ step.content }}</pre>
          <span
              v-if="step.status === STEP_STATUS.RUNNING && streaming"
              class="chat-process-step-cursor"
          />
        </template>

        <!-- skill -->
        <template v-else-if="step.type === STEP_TYPES.SKILL">
          <div v-if="step.input" class="chat-process-block">
            <span class="chat-process-block-label">输入</span>
            <pre class="chat-process-step-content">{{ formatJsonBlock(step.input) }}</pre>
          </div>
          <div v-if="step.output" class="chat-process-block">
            <span class="chat-process-block-label">输出</span>
            <pre class="chat-process-step-content">{{ step.output }}</pre>
          </div>
          <p
              v-if="step.status === STEP_STATUS.RUNNING && !step.output"
              class="chat-process-step-placeholder"
          >
            技能执行中…
          </p>
        </template>

        <!-- mcp -->
        <template v-else-if="step.type === STEP_TYPES.MCP">
          <div v-if="step.arguments" class="chat-process-block">
            <span class="chat-process-block-label">参数</span>
            <pre class="chat-process-step-content">{{ formatJsonBlock(step.arguments) }}</pre>
          </div>
          <div v-if="step.result" class="chat-process-block">
            <span class="chat-process-block-label">结果</span>
            <pre class="chat-process-step-content">{{ step.result }}</pre>
          </div>
          <p
              v-if="step.status === STEP_STATUS.RUNNING && !step.result"
              class="chat-process-step-placeholder"
          >
            工具调用中…
          </p>
        </template>

        <!-- fallback -->
        <template v-else>
          <pre class="chat-process-step-content">{{ step.content }}</pre>
        </template>
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

.chat-process-block + .chat-process-block {
  margin-top: 8px;
}

.chat-process-block-label {
  display: block;
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--chat-muted-text, #a3a3a3);
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

.chat-process-step-placeholder {
  margin: 0;
  font-size: 12px;
  color: var(--chat-muted-text, #a3a3a3);
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
