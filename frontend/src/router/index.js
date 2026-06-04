import { createRouter, createWebHistory } from 'vue-router'
import { setupRouterGuard } from './guard/index.js'
import { basicRoutes, EMPTY_ROUTE, NOT_FOUND_ROUTE } from './routes/index.js'
import { getToken, isNullOrWhitespace } from '@/utils'
import { useUserStore } from '@/store'

export const router = createRouter({
  history: createWebHistory('/'),
  routes: basicRoutes,
  scrollBehavior: () => ({ left: 0, top: 0 }),
})

export async function setupRouter(app) {
  await addDynamicRoutes()
  setupRouterGuard(router)
  app.use(router)
}

export async function resetRouter() {
  const basicRouteNames = getRouteNames(basicRoutes)
  router.getRoutes().forEach((route) => {
    const name = route.name
    if (!basicRouteNames.includes(name)) {
      router.removeRoute(name)
    }
  })
}

export async function addDynamicRoutes() {
  const token = getToken()

  if (isNullOrWhitespace(token)) {
    router.addRoute(EMPTY_ROUTE)
    return
  }

  const userStore = useUserStore()
  if (!userStore.userId) {
    await userStore.getUserInfo()
  }

  if (router.hasRoute(EMPTY_ROUTE.name)) {
    router.removeRoute(EMPTY_ROUTE.name)
  }
  if (!router.hasRoute(NOT_FOUND_ROUTE.name)) {
    router.addRoute(NOT_FOUND_ROUTE)
  }
}

export function getRouteNames(routes) {
  return routes.map((route) => getRouteName(route)).flat(1)
}

function getRouteName(route) {
  const names = [route.name]
  if (route.children?.length) {
    names.push(...route.children.map((item) => getRouteName(item)).flat(1))
  }
  return names
}

export default router
