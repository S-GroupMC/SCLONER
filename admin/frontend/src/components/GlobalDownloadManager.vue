<template>
  <div>
    <!-- Кнопка в навбаре -->
    <button 
      @click="isOpen = true"
      class="relative px-4 py-2 rounded-lg hover:bg-white/10 transition-colors flex items-center"
      :class="activeDownloads.length > 0 ? 'bg-white/10' : ''"
    >
      <i class="fas fa-tasks mr-2"></i>
      <span>Загрузки</span>
      <span 
        v-if="activeDownloads.length > 0" 
        class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs flex items-center justify-center font-bold animate-pulse"
      >
        {{ activeDownloads.length }}
      </span>
    </button>

    <!-- Модальное окно -->
    <Teleport to="body">
      <div v-if="isOpen" class="fixed inset-0 z-[100] flex items-center justify-center">
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="isOpen = false"></div>
        
        <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-4xl mx-4 max-h-[85vh] flex flex-col overflow-hidden">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 bg-gradient-to-r from-gray-900 to-gray-800 text-white">
            <div class="flex items-center space-x-3">
              <i class="fas fa-tasks text-xl"></i>
              <h2 class="text-lg font-bold">Менеджер загрузок</h2>
              <span class="px-2 py-0.5 bg-white/20 rounded-full text-sm">{{ downloads.length }} всего</span>
              <span v-if="activeDownloads.length > 0" class="px-2 py-0.5 bg-green-500 rounded-full text-sm">
                {{ activeDownloads.length }} активных
              </span>
            </div>
            <div class="flex items-center space-x-2">
              <button 
                v-if="activeDownloads.length > 0"
                @click="pauseAll"
                class="p-2 hover:bg-white/20 rounded-lg transition-colors"
                title="Пауза всех"
              >
                <i class="fas fa-pause"></i>
              </button>
              <button 
                v-if="pausedDownloads.length > 0"
                @click="resumeAll"
                class="p-2 hover:bg-white/20 rounded-lg transition-colors"
                title="Продолжить все"
              >
                <i class="fas fa-play"></i>
              </button>
              <button 
                @click="clearCompleted"
                class="p-2 hover:bg-white/20 rounded-lg transition-colors"
                title="Очистить завершённые"
              >
                <i class="fas fa-broom"></i>
              </button>
              <button 
                @click="refreshJobs"
                class="p-2 hover:bg-white/20 rounded-lg transition-colors"
                title="Обновить"
              >
                <i class="fas fa-sync-alt"></i>
              </button>
              <button 
                @click="isOpen = false"
                class="p-2 hover:bg-white/20 rounded-lg transition-colors"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>
          </div>

          <!-- Tabs -->
          <div class="flex border-b bg-gray-50">
            <button 
              @click="activeTab = 'all'"
              class="px-4 py-2 text-sm font-medium transition-colors"
              :class="activeTab === 'all' ? 'text-blue-600 border-b-2 border-blue-600 bg-white' : 'text-gray-600 hover:text-gray-900'"
            >
              Все ({{ downloads.length }})
            </button>
            <button 
              @click="activeTab = 'active'"
              class="px-4 py-2 text-sm font-medium transition-colors"
              :class="activeTab === 'active' ? 'text-blue-600 border-b-2 border-blue-600 bg-white' : 'text-gray-600 hover:text-gray-900'"
            >
              Активные ({{ activeDownloads.length }})
            </button>
            <button 
              @click="activeTab = 'completed'"
              class="px-4 py-2 text-sm font-medium transition-colors"
              :class="activeTab === 'completed' ? 'text-blue-600 border-b-2 border-blue-600 bg-white' : 'text-gray-600 hover:text-gray-900'"
            >
              Завершённые ({{ completedDownloads.length }})
            </button>
            <button 
              @click="activeTab = 'failed'"
              class="px-4 py-2 text-sm font-medium transition-colors"
              :class="activeTab === 'failed' ? 'text-blue-600 border-b-2 border-blue-600 bg-white' : 'text-gray-600 hover:text-gray-900'"
            >
              Ошибки ({{ failedDownloads.length }})
            </button>
          </div>

          <!-- Downloads list -->
          <div class="flex-1 overflow-y-auto">
            <div v-if="filteredDownloads.length === 0" class="p-12 text-center text-gray-500">
              <i class="fas fa-inbox text-5xl mb-4"></i>
              <p class="text-lg">Нет загрузок</p>
              <p class="text-sm mt-2">Загрузки появятся здесь когда вы начнёте скачивать сайты</p>
            </div>
            
            <div v-else class="divide-y divide-gray-100">
              <div 
                v-for="job in filteredDownloads" 
                :key="job.id"
                class="p-4 hover:bg-gray-50 transition-colors"
              >
                <div class="flex items-start justify-between">
                  <!-- Info -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center space-x-3 mb-2">
                      <i :class="getStatusIcon(job.status)" class="text-lg"></i>
                      <span class="font-semibold text-gray-900 truncate">{{ job.domain || getDomainFromUrl(job.url) }}</span>
                      <span class="text-xs text-gray-500 font-mono">ID: {{ job.id }}</span>
                      <span v-if="job.pid" class="text-xs text-gray-400 font-mono">PID: {{ job.pid }}</span>
                    </div>
                    
                    <div class="text-sm text-gray-500 mb-2 truncate">
                      <i class="fas fa-link mr-1"></i>{{ job.url }}
                    </div>
                    
                    <!-- Progress bar -->
                    <div v-if="job.status === 'running' || job.status === 'paused'" class="mb-2">
                      <div class="flex items-center space-x-3">
                        <div class="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div 
                            class="h-full transition-all duration-300"
                            :class="job.status === 'paused' ? 'bg-yellow-500' : 'bg-gradient-to-r from-blue-500 to-purple-500'"
                            :style="{ width: (job.progress || 0) + '%' }"
                          ></div>
                        </div>
                        <span class="text-sm font-medium text-gray-700 w-12 text-right">{{ job.progress || 0 }}%</span>
                      </div>
                    </div>
                    
                    <!-- Stats -->
                    <div class="flex items-center space-x-4 text-xs text-gray-500">
                      <span v-if="job.files_downloaded">
                        <i class="fas fa-file mr-1"></i>{{ job.files_downloaded }} файлов
                      </span>
                      <span v-if="job.engine">
                        <i class="fas fa-cog mr-1"></i>{{ job.engine }}
                      </span>
                      <span v-if="job.folder_name">
                        <i class="fas fa-folder mr-1"></i>{{ job.folder_name }}
                      </span>
                      <span :class="getStatusTextClass(job.status)">
                        {{ getStatusText(job.status) }}
                      </span>
                    </div>
                    
                    <!-- Last log line -->
                    <div v-if="job.output_lines?.length > 0" class="mt-2 text-xs text-gray-400 font-mono truncate">
                      {{ job.output_lines[job.output_lines.length - 1] }}
                    </div>
                  </div>
                  
                  <!-- Actions -->
                  <div class="flex items-center space-x-1 ml-4">
                    <button 
                      v-if="job.status === 'running'"
                      @click="pauseJob(job.id)"
                      class="p-2 text-yellow-600 hover:bg-yellow-50 rounded-lg transition-colors"
                      title="Пауза"
                    >
                      <i class="fas fa-pause"></i>
                    </button>
                    <button 
                      v-if="job.status === 'paused'"
                      @click="resumeJob(job.id)"
                      class="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                      title="Продолжить"
                    >
                      <i class="fas fa-play"></i>
                    </button>
                    <button 
                      @click="showLogs(job)"
                      class="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="Логи"
                    >
                      <i class="fas fa-terminal"></i>
                    </button>
                    <button 
                      v-if="job.status === 'completed' || job.status === 'failed'"
                      @click="restartJob(job.id)"
                      class="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      title="Перезапустить"
                    >
                      <i class="fas fa-redo"></i>
                    </button>
                    <button 
                      @click="deleteJob(job.id)"
                      class="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Удалить"
                    >
                      <i class="fas fa-trash"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Logs Modal -->
      <div v-if="logsModal" class="fixed inset-0 z-[110] flex items-center justify-center">
        <div class="absolute inset-0 bg-black/50" @click="logsModal = null"></div>
        <div class="relative bg-white rounded-xl shadow-2xl w-full max-w-4xl mx-4 max-h-[80vh] flex flex-col">
          <div class="flex items-center justify-between p-4 border-b bg-gray-900 text-white rounded-t-xl">
            <div class="flex items-center space-x-3">
              <i class="fas fa-terminal"></i>
              <span class="font-bold">Логи: {{ logsModal.domain || getDomainFromUrl(logsModal.url) }}</span>
              <span class="text-xs text-gray-400">ID: {{ logsModal.id }}</span>
            </div>
            <button @click="logsModal = null" class="text-gray-400 hover:text-white">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div 
            ref="logsContainer"
            class="flex-1 overflow-y-auto bg-gray-900 p-4 font-mono text-xs text-green-400"
          >
            <div v-for="(line, i) in logsModal.output_lines" :key="i" class="py-0.5 hover:bg-gray-800">
              {{ line }}
            </div>
            <div v-if="!logsModal.output_lines?.length" class="text-gray-500">
              Логи пока пусты...
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const isOpen = ref(false)
const activeTab = ref('all')
const downloads = ref([])
const logsModal = ref(null)
const logsContainer = ref(null)

let pollInterval = null

const activeDownloads = computed(() => downloads.value.filter(d => d.status === 'running'))
const pausedDownloads = computed(() => downloads.value.filter(d => d.status === 'paused'))
const completedDownloads = computed(() => downloads.value.filter(d => d.status === 'completed'))
const failedDownloads = computed(() => downloads.value.filter(d => d.status === 'failed' || d.status === 'stopped'))

const filteredDownloads = computed(() => {
  switch (activeTab.value) {
    case 'active': return [...activeDownloads.value, ...pausedDownloads.value]
    case 'completed': return completedDownloads.value
    case 'failed': return failedDownloads.value
    default: return downloads.value
  }
})

function getDomainFromUrl(url) {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

function getStatusIcon(status) {
  switch (status) {
    case 'running': return 'fas fa-spinner fa-spin text-blue-500'
    case 'paused': return 'fas fa-pause-circle text-yellow-500'
    case 'completed': return 'fas fa-check-circle text-green-500'
    case 'failed': return 'fas fa-times-circle text-red-500'
    case 'stopped': return 'fas fa-stop-circle text-orange-500'
    case 'pending': return 'fas fa-clock text-gray-400'
    default: return 'fas fa-question-circle text-gray-400'
  }
}

function getStatusText(status) {
  switch (status) {
    case 'running': return 'Загрузка...'
    case 'paused': return 'Пауза'
    case 'completed': return 'Завершено'
    case 'failed': return 'Ошибка'
    case 'stopped': return 'Остановлено'
    case 'pending': return 'Ожидание'
    default: return status
  }
}

function getStatusTextClass(status) {
  switch (status) {
    case 'running': return 'text-blue-600'
    case 'paused': return 'text-yellow-600'
    case 'completed': return 'text-green-600'
    case 'failed': return 'text-red-600'
    case 'stopped': return 'text-orange-600'
    default: return 'text-gray-500'
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options)
  return response.json()
}

async function refreshJobs() {
  try {
    const data = await fetchJson('/api/jobs')
    downloads.value = data.sort((a, b) => {
      const order = { running: 0, paused: 1, pending: 2, completed: 3, failed: 4, stopped: 5 }
      return (order[a.status] || 6) - (order[b.status] || 6)
    })
  } catch (err) {
    console.error('Error fetching jobs:', err)
  }
}

async function pauseJob(id) {
  try {
    await fetchJson(`/api/jobs/${id}/pause`, { method: 'POST' })
    refreshJobs()
  } catch (err) {
    console.error('Error pausing job:', err)
  }
}

async function resumeJob(id) {
  try {
    await fetchJson(`/api/jobs/${id}/resume`, { method: 'POST' })
    refreshJobs()
  } catch (err) {
    console.error('Error resuming job:', err)
  }
}

async function deleteJob(id) {
  if (!confirm('Удалить эту загрузку?')) return
  try {
    await fetchJson(`/api/jobs/${id}`, { method: 'DELETE' })
    downloads.value = downloads.value.filter(d => d.id !== id)
  } catch (err) {
    console.error('Error deleting job:', err)
  }
}

async function restartJob(id) {
  try {
    await fetchJson(`/api/jobs/${id}/restart`, { method: 'POST' })
    refreshJobs()
  } catch (err) {
    console.error('Error restarting job:', err)
  }
}

function pauseAll() {
  activeDownloads.value.forEach(d => pauseJob(d.id))
}

function resumeAll() {
  pausedDownloads.value.forEach(d => resumeJob(d.id))
}

function clearCompleted() {
  completedDownloads.value.forEach(d => deleteJob(d.id))
  failedDownloads.value.forEach(d => deleteJob(d.id))
}

function showLogs(job) {
  logsModal.value = job
}

function startPolling() {
  if (pollInterval) return
  pollInterval = setInterval(refreshJobs, 3000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

watch(isOpen, (val) => {
  if (val) {
    refreshJobs()
    startPolling()
  } else {
    stopPolling()
  }
})

watch(() => logsModal.value?.output_lines?.length, () => {
  if (logsContainer.value) {
    setTimeout(() => {
      logsContainer.value.scrollTop = logsContainer.value.scrollHeight
    }, 50)
  }
})

onMounted(() => {
  refreshJobs()
  // Poll in background for badge
  setInterval(refreshJobs, 10000)
})

onUnmounted(() => {
  stopPolling()
})
</script>
