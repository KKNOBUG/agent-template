import { useUserStore } from '@/store'

let isHandlingUnauthorized = false

export function isUnauthorizedCode(code) {
    return ['401', '400401'].includes(String(code))
}

/** Token 失效时调用退出接口并清理本地登录态 */
export async function handleUnauthorized() {
    if (isHandlingUnauthorized) return
    isHandlingUnauthorized = true
    try {
        const userStore = useUserStore()
        await userStore.logout({ callApi: true })
    } finally {
        isHandlingUnauthorized = false
    }
}
