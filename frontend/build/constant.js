export const OUTPUT_DIR = 'dist'

// export const BACKEND_URL = 'http://172.20.10.2:8519'
export const BACKEND_URL = 'http://192.168.1.6:8519'

export const PROXY_CONFIG = {
  /**
   * 前端请求 /api/xxx，代理转发时去掉 /api 前缀，后端路由为 /xxx
   * 例：http://localhost:3100/api/base/auth/access_token → http://backend/base/auth/access_token
   */
  '/api': {
    target: BACKEND_URL,
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
}

export const EXTRA_DEV_PROXY = {}
