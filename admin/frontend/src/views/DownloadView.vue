<template>
  <div>
    <ActiveDownloads />
    
    <div class="card max-w-2xl mx-auto">
      <h2 class="text-2xl font-bold text-gray-900 mb-6">
        <i class="fas fa-download mr-2 text-blue-600"></i>
        Скачать новый сайт
      </h2>
      
      <form @submit.prevent="prepareLanding" class="space-y-6">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Домен или URL сайта
          </label>
          <input 
            v-model="url"
            type="text"
            required
            placeholder="example.com"
            class="input text-lg"
            autofocus
          />
          <p class="text-xs text-gray-500 mt-2">
            Введите домен (example.com) или полный URL. После создания папки откроется страница анализа.
          </p>
        </div>
        
        <div class="flex items-center justify-end pt-4 border-t">
          <button 
            type="submit"
            :disabled="loading || !url"
            class="btn btn-primary px-8"
          >
            <i class="fas mr-2" :class="loading ? 'fa-spinner fa-spin' : 'fa-arrow-right'"></i>
            {{ loading ? 'Создание...' : 'Далее' }}
          </button>
        </div>
      </form>
      
      <!-- Error message -->
      <div v-if="error" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
        <p class="text-red-700 text-sm">{{ error }}</p>
      </div>
    </div>
    
    <!-- Модальное окно выбора платформы (если папка существует) -->
    <Teleport to="body">
      <div v-if="showExistsModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showExistsModal = false">
        <div class="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md mx-4" @click.stop>
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-gray-900">
              <i class="fas fa-folder-open mr-2 text-yellow-500"></i>Папка существует
            </h3>
            <button @click="showExistsModal = false" class="text-gray-400 hover:text-gray-600">
              <i class="fas fa-times"></i>
            </button>
          </div>
          
          <p class="text-sm text-gray-600 mb-4">
            Папка <strong>{{ existingFolder.name }}</strong> уже существует ({{ existingFolder.files }} файлов).
          </p>
          
          <div class="space-y-3 mb-6">
            <button 
              @click="openExisting"
              class="w-full flex items-center p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left"
            >
              <i class="fas fa-external-link-alt text-xl text-blue-500 mr-3"></i>
              <div>
                <div class="font-medium text-gray-900">Открыть существующую</div>
                <div class="text-xs text-gray-500">Перейти к карточке сайта</div>
              </div>
            </button>
            
            <div class="relative">
              <div class="absolute inset-0 flex items-center">
                <div class="w-full border-t border-gray-200"></div>
              </div>
              <div class="relative flex justify-center text-xs">
                <span class="px-2 bg-white text-gray-500">или перекачать</span>
              </div>
            </div>
            
            <div class="grid grid-cols-2 gap-2">
              <button 
                v-for="engine in engines" 
                :key="engine.value"
                @click="redownloadWith(engine.value)"
                class="flex flex-col items-center justify-center p-3 border-2 rounded-lg transition-all hover:border-blue-400 hover:bg-blue-50"
                :class="selectedEngine === engine.value ? 'border-blue-500 bg-blue-50' : 'border-gray-200'"
              >
                <i :class="engine.icon" class="text-2xl mb-1" :style="{ color: engine.color }"></i>
                <div class="font-medium text-sm">{{ engine.label }}</div>
              </button>
            </div>
          </div>
          
          <div class="flex space-x-3">
            <button 
              @click="showExistsModal = false" 
              class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
            >
              Отмена
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ActiveDownloads from '../components/ActiveDownloads.vue'

const router = useRouter()

const url = ref('')
const loading = ref(false)
const error = ref('')
const showExistsModal = ref(false)
const existingFolder = ref({ name: '', files: 0 })
const selectedEngine = ref('wget2')

const engines = [
  { value: 'wget2', label: 'wget2', icon: 'fas fa-bolt', color: '#3b82f6' },
  { value: 'puppeteer', label: 'Puppeteer', icon: 'fas fa-robot', color: '#8b5cf6' },
  { value: 'httrack', label: 'HTTrack', icon: 'fas fa-layer-group', color: '#f59e0b' },
  { value: 'smart', label: 'Smart', icon: 'fas fa-brain', color: '#10b981' }
]

async function prepareLanding() {
  if (!url.value) return
  
  loading.value = true
  error.value = ''
  
  try {
    const res = await fetch('/api/prepare-landing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url.value })
    })
    
    const data = await res.json()
    
    if (res.ok && data.folder_name) {
      if (data.existing) {
        // Show modal with options for existing folder
        existingFolder.value = { name: data.folder_name, files: data.landing_meta?.files_count || 0 }
        showExistsModal.value = true
      } else {
        // Redirect to site details page (no auto-actions)
        router.push(`/site/${data.folder_name}`)
      }
    } else {
      error.value = data.error || data.detail?.error || 'Неизвестная ошибка'
    }
  } catch (err) {
    error.value = 'Ошибка: ' + err.message
  } finally {
    loading.value = false
  }
}

function openExisting() {
  showExistsModal.value = false
  router.push(`/site/${existingFolder.value.name}`)
}

async function redownloadWith(engine) {
  showExistsModal.value = false
  
  // Go to site page (no auto-actions)
  router.push(`/site/${existingFolder.value.name}`)
}
</script>
