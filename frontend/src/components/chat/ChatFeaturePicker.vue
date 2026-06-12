<script setup>
import { computed, ref, watch } from 'vue'
import { NCheckbox, NPopover } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  icon: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    default: '',
  },
  searchPlaceholder: {
    type: String,
    default: '搜索...',
  },
  emptyText: {
    type: String,
    default: '暂无可用项',
  },
  noMatchText: {
    type: String,
    default: '未找到匹配项',
  },
  items: {
    type: Array,
    default: () => [],
  },
  modelValue: {
    type: Array,
    default: () => [],
  },
  allowEmpty: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])

const showPopover = ref(false)
const searchText = ref('')

const filteredItems = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return props.items
  return props.items.filter((item) =>
      (item.label || '').toLowerCase().includes(keyword),
  )
})

const isActive = computed(() => props.modelValue.length > 0)

const isUnavailable = computed(() => props.items.length === 0 && !props.allowEmpty)

const triggerTitle = computed(() => {
  if (props.items.length === 0) return props.emptyText
  return `${props.title}（已选 ${props.modelValue.length}/${props.items.length}）`
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
      :disabled="isUnavailable"
  >
    <template #trigger>
      <button
          type="button"
          class="chat-feature-trigger"
          :class="{ 'is-active': isActive }"
          :disabled="isUnavailable"
          :title="triggerTitle"
      >
        <TheIcon :icon="icon" :size="18" color="#fff" />
      </button>
    </template>

    <div class="chat-feature-panel">
      <div class="chat-feature-search">
        <TheIcon icon="material-symbols:search" :size="14" color="var(--chat-muted-text)" />
        <input
            v-model="searchText"
            class="chat-feature-search-input"
            type="text"
            :placeholder="searchPlaceholder"
            @click.stop
        />
      </div>

      <div v-if="filteredItems.length > 0" class="chat-feature-list">
        <div
            v-for="item in filteredItems"
            :key="item.id"
            class="chat-feature-item"
            :class="{ 'is-selected': isSelected(item.id) }"
            @click="toggleItem(item.id)"
        >
          <NCheckbox
              :checked="isSelected(item.id)"
              @click.stop
              @update:checked="toggleItem(item.id)"
          />
          <span class="chat-feature-item-name">{{ item.label }}</span>
          <span v-if="item.tag" class="chat-feature-item-tag">{{ item.tag }}</span>
        </div>
      </div>

      <div v-else class="chat-feature-empty">
        {{ searchText.trim() ? noMatchText : emptyText }}
      </div>

      <div class="chat-feature-footer">
        已选 {{ modelValue.length }} / {{ items.length }}
      </div>
    </div>
  </NPopover>
</template>

<style scoped>
.chat-feature-trigger {
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

.chat-feature-trigger.is-active {
  opacity: 1;
}

.chat-feature-trigger.is-active:hover:not(:disabled) {
  background: var(--primary-color-hover, #f76b3c);
}

.chat-feature-trigger:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.chat-feature-trigger :deep(.n-icon) {
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-feature-panel {
  width: 300px;
  padding: 8px;
  border-radius: 10px;
  background: var(--chat-input-surface, #fff);
  border: 1px solid var(--chat-input-border, #e8e8e8);
  box-shadow: var(--chat-input-shadow, 0 8px 24px rgba(0, 0, 0, 0.12));
}

.chat-feature-search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border: 1px solid var(--chat-input-border, #e8e8e8);
  border-radius: 6px;
  background: var(--chat-input-surface, #fff);
}

.chat-feature-search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 12px;
  color: var(--n-text-color, #333);
}

.chat-feature-search-input::placeholder {
  color: var(--chat-muted-text, #a3a3a3);
}

.chat-feature-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  margin-top: 8px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #ccc transparent;
}

.chat-feature-list::-webkit-scrollbar {
  width: 5px;
}

.chat-feature-list::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.chat-feature-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--chat-input-border, #e8e8e8);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.chat-feature-item:hover {
  border-color: color-mix(in srgb, var(--primary-color, #f4511e) 30%, var(--chat-input-border, #e8e8e8));
}

.chat-feature-item.is-selected {
  border-color: var(--primary-color, #f4511e);
  background: color-mix(in srgb, var(--primary-color, #f4511e) 8%, var(--chat-input-surface, #fff));
}

.chat-feature-item-name {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  color: var(--n-text-color, #333);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-feature-item-tag {
  flex-shrink: 0;
  padding: 1px 6px;
  border: 1px solid color-mix(in srgb, var(--primary-color, #f4511e) 40%, transparent);
  border-radius: 999px;
  font-size: 10px;
  line-height: 14px;
  color: var(--primary-color, #f4511e);
  white-space: nowrap;
}

.chat-feature-empty {
  margin-top: 8px;
  padding: 20px 10px;
  text-align: center;
  font-size: 12px;
  color: var(--n-text-color-3, #999);
}

.chat-feature-footer {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--chat-input-border, #e8e8e8);
  text-align: right;
  font-size: 11px;
  color: var(--chat-muted-text, #a3a3a3);
}
</style>
