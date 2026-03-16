<template>
  <div>
    <ActiveDownloads />
    
    <div class="card max-w-4xl mx-auto">
      <h2 class="text-2xl font-bold text-gray-900 mb-6">
        <i class="fas fa-download mr-2 text-blue-600"></i>
        Скачать сайт
      </h2>
      
      <form @submit.prevent="startDownload" class="space-y-6">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            URL сайта
          </label>
          <input 
            v-model="form.url"
            type="url"
            required
            placeholder="https://example.com"
            class="input"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Движок скачивания
          </label>
          <div class="grid grid-cols-4 gap-3">
            <label 
              v-for="engine in engines" 
              :key="engine.value"
              class="relative flex items-center justify-center p-4 border-2 rounded-lg cursor-pointer transition-all"
              :class="form.engine === engine.value 
                ? 'border-blue-500 bg-blue-50' 
                : 'border-gray-200 hover:border-gray-300'"
            >
              <input 
                type="radio" 
                v-model="form.engine" 
                :value="engine.value"
                class="sr-only"
              />
              <div class="text-center">
                <i :class="engine.icon" class="text-2xl mb-2" :style="{ color: engine.color }"></i>
                <div class="font-medium text-sm">{{ engine.label }}</div>
              </div>
            </label>
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Глубина рекурсии
            </label>
            <input 
              v-model.number="form.depth"
              type="number"
              min="1"
              max="10"
              class="input"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Имя папки (опционально)
            </label>
            <input 
              v-model="form.folderName"
              type="text"
              placeholder="Авто"
              class="input"
            />
          </div>
        </div>
        
        <div class="space-y-3">
          <label class="flex items-center space-x-3 cursor-pointer">
            <input 
              type="checkbox" 
              v-model="form.recursive"
              class="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
            />
            <span class="text-sm text-gray-700">Рекурсивное скачивание</span>
          </label>
          
          <label class="flex items-center space-x-3 cursor-pointer">
            <input 
              type="checkbox" 
              v-model="form.includeSubdomains"
              class="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
            />
            <span class="text-sm text-gray-700">Включить поддомены</span>
          </label>
          
          <label class="flex items-center space-x-3 cursor-pointer">
            <input 
              type="checkbox" 
              v-model="form.withVueWrapper"
              class="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
            />
            <span class="text-sm text-gray-700">Создать Vue-обёртку</span>
          </label>
        </div>
        
        <div class="flex items-center justify-between pt-4 border-t">
          <button 
            type="button"
            @click="resetForm"
            class="btn btn-secondary"
          >
            <i class="fas fa-redo mr-2"></i>
            Сбросить
          </button>
          
          <button 
            type="submit"
            :disabled="loading"
            class="btn btn-primary"
          >
            <i class="fas mr-2" :class="loading ? 'fa-spinner fa-spin' : 'fa-download'"></i>
            {{ loading ? 'Запуск...' : 'Скачать' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useJobsStore } from '../stores/jobs'
import ActiveDownloads from '../components/ActiveDownloads.vue'

const router = useRouter()
const jobsStore = useJobsStore()

const loading = ref(false)

const engines = [
  { value: 'wget2', label: 'wget2', icon: 'fas fa-bolt', color: '#3b82f6' },
  { value: 'puppeteer', label: 'Puppeteer', icon: 'fas fa-robot', color: '#8b5cf6' },
  { value: 'httrack', label: 'HTTrack', icon: 'fas fa-layer-group', color: '#f59e0b' },
  { value: 'smart', label: 'Smart', icon: 'fas fa-brain', color: '#10b981' }
]

const form = reactive({
  url: '',
  engine: 'wget2',
  depth: 3,
  folderName: '',
  recursive: true,
  includeSubdomains: false,
  withVueWrapper: false
})

function resetForm() {
  form.url = ''
  form.engine = 'wget2'
  form.depth = 3
  form.folderName = ''
  form.recursive = true
  form.includeSubdomains = false
  form.withVueWrapper = false
}

async function startDownload() {
  loading.value = true
  
  try {
    const options = {
      engine: form.engine,
      recursive: form.recursive,
      depth: form.depth,
      include_subdomains: form.includeSubdomains,
      with_vue_wrapper: form.withVueWrapper
    }
    
    if (form.folderName) {
      options.folder_name = form.folderName
    }
    
    await jobsStore.startJob(form.url, options)
    
    router.push('/landings')
  } catch (error) {
    alert('Ошибка запуска: ' + error.message)
  } finally {
    loading.value = false
  }
}
</script>
