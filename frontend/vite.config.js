import { defineConfig, loadEnv } from 'vite'
import { convertEnv, getRootPath, getSrcPath } from './build/utils.js'
import { viteDefine } from './build/config/index.js'
import { createVitePlugins } from './build/plugin/index.js'
import { BACKEND_URL, OUTPUT_DIR } from './build/constant.js'

export default defineConfig(({ command, mode }) => {
  const srcPath = getSrcPath()
  const rootPath = getRootPath()
  const isBuild = command === 'build'
  const isDev = command === 'serve'

  const env = loadEnv(mode, process.cwd())
  const viteEnv = convertEnv(env)
  const { VITE_PORT, VITE_PUBLIC_PATH, VITE_USE_PROXY } = viteEnv

  const enableProxy = isDev && VITE_USE_PROXY !== false

  return {
    base: VITE_PUBLIC_PATH || '/',
    resolve: {
      alias: {
        '~': rootPath,
        '@': srcPath,
      },
    },
    define: viteDefine,
    plugins: createVitePlugins(viteEnv, isBuild),
    server: {
      host: '0.0.0.0',
      port: VITE_PORT,
      proxy: enableProxy
        ? {
            '/api': {
              target: BACKEND_URL,
              changeOrigin: true,
            },
          }
        : undefined,
    },
    build: {
      target: 'es2015',
      outDir: OUTPUT_DIR || 'dist',
      reportCompressedSize: false,
      chunkSizeWarningLimit: 1024,
    },
  }
})
