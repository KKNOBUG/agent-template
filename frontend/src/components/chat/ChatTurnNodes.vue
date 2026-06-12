<script setup>
import { ref, watch, nextTick } from 'vue'
import MiddleEllipsisText from './MiddleEllipsisText.vue'

const props = defineProps({
  turns: {
    type: Array,
    default: () => [],
  },
  activeTurnIndex: {
    type: Number,
    default: 0,
  },
  kbLabel: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['select'])

const isExpanded = ref(false)
const hoveredIndex = ref(null)
const listRef = ref(null)
const itemRefs = ref([])

function setItemRef(el, index) {
  if (el) {
    itemRefs.value[index] = el
  }
}

function handleSelect(turnIndex) {
  emit('select', turnIndex)
}

watch(
    () => props.activeTurnIndex,
    async () => {
      if (!isExpanded.value) return
      await nextTick()
      const el = itemRefs.value[props.activeTurnIndex]
      const list = listRef.value
      if (!el || !list) return

      const elTop = el.offsetTop
      const elBottom = elTop + el.offsetHeight
      const viewTop = list.scrollTop
      const viewBottom = viewTop + list.clientHeight

      if (elTop < viewTop) {
        list.scrollTop = elTop
      } else if (elBottom > viewBottom) {
        list.scrollTop = elBottom - list.clientHeight
      }
    },
)
</script>

<template>
  <div
      class="chat-turn-nodes-root"
      :class="{ 'is-expanded': isExpanded }"
      @mouseenter="isExpanded = true"
      @mouseleave="isExpanded = false; hoveredIndex = null"
  >
    <div class="chat-turn-nodes-shell">
      <div v-if="kbLabel" class="chat-turn-nodes-header">
        <MiddleEllipsisText class="chat-turn-nodes-kb" :text="kbLabel" />
      </div>

      <div ref="listRef" class="chat-turn-nodes-list">
        <button
            v-for="turn in turns"
            :key="turn.turnIndex"
            :ref="(el) => setItemRef(el, turn.turnIndex)"
            type="button"
            class="chat-turn-nodes-item"
            :class="{
              'is-active': activeTurnIndex === turn.turnIndex,
              'is-hovered': hoveredIndex === turn.turnIndex,
            }"
            @mouseenter="hoveredIndex = turn.turnIndex"
            @mouseleave="hoveredIndex = null"
            @click="handleSelect(turn.turnIndex)"
        >
          <span class="chat-turn-nodes-label">{{ turn.label }}</span>
          <span class="chat-turn-nodes-dash" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-turn-nodes-root {
  display: flex;
  justify-content: flex-end;
  pointer-events: auto;
}

.chat-turn-nodes-shell {
  overflow: hidden;
  border-radius: 16px;
  transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.chat-turn-nodes-root.is-expanded .chat-turn-nodes-shell {
  background: var(--chat-input-surface, #fff);
  border: 1px solid var(--chat-input-border, #e8e8e8);
  box-shadow: var(--chat-input-shadow, 0 4px 16px rgba(0, 0, 0, 0.1));
}

.chat-turn-nodes-header {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  padding: 0 12px;
  border-bottom: 1px solid transparent;
  transition: max-height 0.2s ease, opacity 0.15s ease, padding 0.2s ease, border-color 0.15s ease;
}

.chat-turn-nodes-root.is-expanded .chat-turn-nodes-header {
  max-height: 40px;
  opacity: 1;
  padding: 10px 12px 8px;
  border-bottom-color: var(--chat-input-border, #e8e8e8);
}

.chat-turn-nodes-kb {
  display: block;
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: var(--n-text-color-2, #666);
}

.chat-turn-nodes-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 126px;
  padding: 8px 4px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: transparent transparent;
}

.chat-turn-nodes-root.is-expanded .chat-turn-nodes-list {
  padding: 8px 4px 8px 12px;
  scrollbar-color: #ccc transparent;
}

.chat-turn-nodes-list::-webkit-scrollbar {
  width: 3px;
}

.chat-turn-nodes-list::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 2px;
}

.chat-turn-nodes-root.is-expanded .chat-turn-nodes-list::-webkit-scrollbar-thumb {
  background: #ccc;
}

.chat-turn-nodes-item {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
  min-height: 16px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--n-text-color-3, #ccc);
  transition: color 0.15s ease;
}

.chat-turn-nodes-item.is-hovered {
  color: var(--n-text-color, #333);
}

.chat-turn-nodes-item.is-active {
  color: var(--primary-color, #f4511e);
}

.chat-turn-nodes-label {
  flex: 0 1 auto;
  max-width: 0;
  opacity: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 11px;
  line-height: 16px;
  text-align: right;
  transition: max-width 0.2s ease, opacity 0.15s ease;
}

.chat-turn-nodes-root.is-expanded .chat-turn-nodes-label {
  max-width: 140px;
  opacity: 1;
}

.chat-turn-nodes-dash {
  flex-shrink: 0;
  width: 14px;
  height: 2px;
  border-radius: 1px;
  background: currentColor;
}
</style>
