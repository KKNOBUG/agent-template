<template>
  <router-view v-slot="{ Component, route }">
    <KeepAlive :include="keepAliveComponentNames">
      <component
          :is="Component"
          v-if="appStore.reloadFlag"
          :key="resolveRouteKey(route)"
      />
    </KeepAlive>
  </router-view>
</template>

<script setup>
import { useAppStore } from '@/store'
import { router } from '@/router'

const appStore = useAppStore()

function resolveRouteKey(route) {
  if (appStore.aliveKeys[route.name]) {
    return appStore.aliveKeys[route.name]
  }
  // keepAlive 页面仅用 route.name 作为 key，避免 query 变化导致整页 remount
  if (route.meta?.keepAlive) {
    return route.name
  }
  return route.fullPath
}

function collectKeepAliveNames(routes, result = []) {
  for (const r of routes) {
    if (r.meta?.keepAlive) {
      const name = r.meta.componentName || r.name
      if (name && !result.includes(name)) result.push(name)
    }
    if (r.children?.length) collectKeepAliveNames(r.children, result)
  }
  return result
}

const keepAliveComponentNames = computed(() => collectKeepAliveNames(router.getRoutes()))
</script>
