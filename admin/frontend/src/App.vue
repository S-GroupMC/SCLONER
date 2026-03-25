<template>
  <div class="min-h-screen bg-gray-50">
    <nav class="bg-gradient-to-r from-gray-900 to-gray-800 text-white shadow-lg">
      <div class="container mx-auto px-4">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center space-x-3">
            <div class="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
              <span class="text-white text-xl">🐰</span>
            </div>
            <h1 class="text-xl font-bold">Black Rabbit Cloner</h1>
          </div>
          <div class="flex items-center space-x-2">
            <router-link 
              to="/landings" 
              class="px-4 py-2 rounded-lg hover:bg-white/10 transition-colors"
              active-class="bg-white/20"
            >
              <i class="fas fa-globe mr-2"></i>Лендинги
            </router-link>
            <router-link 
              to="/download" 
              class="px-4 py-2 rounded-lg hover:bg-white/10 transition-colors"
              active-class="bg-white/20"
            >
              <i class="fas fa-download mr-2"></i>Скачать
            </router-link>
            <GlobalDownloadManager />
          </div>
        </div>
      </div>
    </nav>

    <main class="container mx-auto px-4 py-6">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useJobsStore } from './stores/jobs'
import GlobalDownloadManager from './components/GlobalDownloadManager.vue'

const jobsStore = useJobsStore()

onMounted(() => {
  jobsStore.initSocket()
})
</script>
