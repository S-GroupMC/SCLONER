import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

// Router configuration
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: App,
      props: route => ({
        landing: {},
        editorMode: false
      })
    }
  ]
})

const app = createApp(App)
app.use(router)
app.mount('#app')
