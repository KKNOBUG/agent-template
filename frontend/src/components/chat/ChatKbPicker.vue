<script setup>
import { computed, ref, watch } from 'vue'
import { NCheckbox, NPopover } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  modelValue: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue'])

const showPopover = ref(false)
const searchText = ref('')

const filteredItems = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return props.items
  return props.items.filter((item) =>
      (item.knowledge_name || '').toLowerCase().includes(keyword),
  )
})

function isSelected(id) {
  return props.modelValue.includes(id)
}

function toggleItem(id) {
  const next = [...props.modelValue]
  const idx = next.indexOf(id)
  if (idx >= 0) {
    next.splice(idx, 1)
  } else {
    next.push(id)
  }
  emit('update:modelValue', next)
}

watch(showPopover, (visible) => {
  if (!visible) {
    searchText.value = ''
  }
})
</script>

<template>
  <NPopover
      v-model:show="showPopover"
      trigger="click"
      placement="top-start"
      :show-arrow="true"
      raw
      :disabled="items.length === 0"
  >
    <template #trigger>
      <button
          type="button"
          class="chat-kb-trigger"
          :class="{ 'is-active': modelValue.length > 0 }"
          :disabled="items.length === 0"
          :title="items.length === 0 ? '暂无可用知识库' : `选择知识库（已选 ${modelValue.length}/${items.length}）`"
      >
        <TheIcon icon="hugeicons:book-open-02" :size="18" color="#fff" />
      </button>
    </template>

    <div class="chat-kb-panel">
      <div class="chat-kb-search">
        <TheIcon icon="material-symbols:search" :size="16" color="var(--chat-muted-text)" />
        <input
            v-model="searchText"
            class="chat-kb-search-input"
            type="text"
            placeholder="搜索知识库..."
            @click.stop
        />
      </div>

      <div v-if="filteredItems.length > 0" class="chat-kb-list">
        <div
            v-for="item in filteredItems"
            :key="item.id"
            class="chat-kb-item"
            :class="{ 'is-selected': isSelected(item.id) }"
            @click="toggleItem(item.id)"
        >
          <NCheckbox
              :checked="isSelected(item.id)"
              @click.stop
              @update:checked="toggleItem(item.id)"
          />
          <span class="chat-kb-item-name">{{ item.knowledge_name }}</span>
          <span v-if="item.document_count != null" class="chat-kb-item-tag">
            {{ item.document_count }} 篇文档
          </span>
        </div>
      </div>

      <div v-else class="chat-kb-empty">
        {{ searchText.trim() ? '未找到匹配的知识库' : '暂无可用知识库' }}
      </div>

      <div class="chat-kb-footer">
        已选 {{ modelValue.length }} / {{ items.length }}
      </div>
    </div>
  </NPopover>
</template>

<style scoped>
.chat-kb-trigger {
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

.chat-kb-trigger.is-active {
  opacity: 1;
}

.chat-kb-trigger.is-active:hover:not(:disabled) {
  background: var(--primary-color-hover, #f76b3c);
}

.chat-kb-trigger:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.chat-kb-trigger :deep(.n-icon) {
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-kb-panel {
  width: 320px;
  padding: 10px;
  border-radius: 12px;
  background: var(--chat-input-surface, #fff);
  border: 1px solid var(--chat-input-border, #e8e8e8);
  box-shadow: var(--chat-input-shadow, 0 8px 24px rgba(0, 0, 0, 0.12));
}

.chat-kb-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--chat-input-border, #e8e8e8);
  border-radius: 8px;
  background: var(--chat-input-surface, #fff);
}

.chat-kb-search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--n-text-color, #333);
}

.chat-kb-search-input::placeholder {
  color: var(--chat-muted-text, #a3a3a3);
}

.chat-kb-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  margin-top: 10px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #ccc transparent;
}

.chat-kb-list::-webkit-scrollbar {
  width: 6px;
}

.chat-kb-list::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.chat-kb-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--chat-input-border, #e8e8e8);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.chat-kb-item:hover {
  border-color: color-mix(in srgb, var(--primary-color, #f4511e) 30%, var(--chat-input-border, #e8e8e8));
}

.chat-kb-item.is-selected {
  border-color: var(--primary-color, #f4511e);
  background: color-mix(in srgb, var(--primary-color, #f4511e) 8%, var(--chat-input-surface, #fff));
}

.chat-kb-item-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--n-text-color, #333);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-kb-item-tag {
  flex-shrink: 0;
  padding: 2px 8px;
  border: 1px solid color-mix(in srgb, var(--primary-color, #f4511e) 40%, transparent);
  border-radius: 999px;
  font-size: 11px;
  line-height: 16px;
  color: var(--primary-color, #f4511e);
  white-space: nowrap;
}

.chat-kb-empty {
  margin-top: 10px;
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--n-text-color-3, #999);
}

.chat-kb-footer {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--chat-input-border, #e8e8e8);
  text-align: right;
  font-size: 12px;
  color: var(--chat-muted-text, #a3a3a3);
}
</style>
