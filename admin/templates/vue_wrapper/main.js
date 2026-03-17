import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

// Simple router - App.vue handles everything via iframe
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/:pathMatch(.*)*',
      component: App
    }
  ]
})

const app = createApp(App)
app.use(router)
app.mount('#app')
