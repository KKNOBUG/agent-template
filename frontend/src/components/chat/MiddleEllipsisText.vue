<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  text: {
    type: String,
    default: '',
  },
  ellipsis: {
    type: String,
    default: '......',
  },
})

const rootRef = ref(null)
const displayText = ref(props.text)

function truncateMiddleToWidth(text, maxWidth, ctx) {
  if (!text) return ''
  if (ctx.measureText(text).width <= maxWidth) return text

  const { ellipsis } = props
  let low = 0
  let high = text.length
  let best = ellipsis

  while (low <= high) {
    const totalKeep = Math.floor((low + high) / 2)
    if (totalKeep <= 0) break

    const headLen = Math.ceil(totalKeep / 2)
    const tailLen = Math.floor(totalKeep / 2)
    const candidate = text.slice(0, headLen) + ellipsis + text.slice(text.length - tailLen)

    if (ctx.measureText(candidate).width <= maxWidth) {
      best = candidate
      low = totalKeep + 1
    } else {
      high = totalKeep - 1
    }
  }

  return best
}

function measure() {
  const el = rootRef.value
  if (!el) return

  const text = props.text || ''
  const maxWidth = el.clientWidth
  if (maxWidth <= 0) {
    displayText.value = text
    return
  }

  if (!text) {
    displayText.value = ''
    return
  }

  const style = window.getComputedStyle(el)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    displayText.value = text
    return
  }

  ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
  displayText.value = truncateMiddleToWidth(text, maxWidth, ctx)
}

let resizeObserver

onMounted(async () => {
  await nextTick()
  measure()
  resizeObserver = new ResizeObserver(() => {
    measure()
  })
  if (rootRef.value) {
    resizeObserver.observe(rootRef.value)
  }
})

watch(
  () => props.text,
  async () => {
    await nextTick()
    measure()
  },
)

onUnmounted(() => {
  resizeObserver?.disconnect()
})
</script>

<template>
  <span
      ref="rootRef"
      class="middle-ellipsis-text"
      :title="text"
  >{{ displayText }}</span>
</template>

<style scoped>
.middle-ellipsis-text {
  display: block;
  width: 100%;
  overflow: hidden;
  white-space: nowrap;
}
</style>
