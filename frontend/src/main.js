import '@/styles/reset.css'
import 'virtual:uno.css'
import '@/styles/global.scss'

import { createApp } from 'vue'
import { setupRouter } from '@/router'
import { setupStore } from '@/store'
import App from './App.vue'
import i18n from '~/i18n'

async function setupApp() {
  const app = createApp(App)
  setupStore(app)
  await setupRouter(app)
  app.use(i18n)
  app.mount('#app')
}

setupApp()
