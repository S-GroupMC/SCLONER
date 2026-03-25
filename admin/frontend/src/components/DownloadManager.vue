<template>
  <div class="download-manager">
    <!-- Плавающая кнопка менеджера загрузок -->
    <button 
      v-if="activeDownloads.length > 0 && !isExpanded"
      @click="isExpanded = true"
      class="fixed bottom-4 right-4 z-50 flex items-center space-x-2 px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-full shadow-lg hover:shadow-xl transition-all"
    >
      <i class="fas fa-download"></i>
      <span class="font-medium">{{ activeDownloads.length }} загрузок</span>
      <span v-if="totalProgress > 0" class="text-xs opacity-75">{{ totalProgress }}%</span>
    </button>

    <!-- Панель менеджера загрузок -->
    <div 
      v-if="isExpanded"
      class="fixed bottom-4 right-4 z-50 w-[500px] max-h-[70vh] bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white">
        <div class="flex items-center space-x-2">
          <i class="fas fa-download"></i>
          <span class="font-bold">Менеджер загрузок</span>
          <span class="px-2 py-0.5 bg-white/20 rounded-full text-xs">{{ downloads.length }}</span>
        </div>
        <div class="flex items-center space-x-2">
          <button 
            v-if="activeDownloads.length > 0"
            @click="pauseAll"
            class="p-1.5 hover:bg-white/20 rounded"
            title="Пауза всех"
          >
            <i class="fas fa-pause"></i>
          </button>
          <button 
            v-if="pausedDownloads.length > 0"
            @click="resumeAll"
            class="p-1.5 hover:bg-white/20 rounded"
            title="Продолжить все"
          >
            <i class="fas fa-play"></i>
          </button>
          <button 
            @click="clearCompleted"
            class="p-1.5 hover:bg-white/20 rounded"
            title="Очистить завершённые"
          >
            <i class="fas fa-broom"></i>
          </button>
          <button 
            @click="isExpanded = false"
            class="p-1.5 hover:bg-white/20 rounded"
          >
            <i class="fas fa-chevron-down"></i>
          </button>
        </div>
      </div>

      <!-- Downloads list -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="downloads.length === 0" class="p-8 text-center text-gray-500">
          <i class="fas fa-inbox text-4xl mb-3"></i>
          <p>Нет активных загрузок</p>
        </div>
        
        <div v-else class="divide-y divide-gray-100">
          <div 
            v-for="download in sortedDownloads" 
            :key="download.id"
            class="p-3 hover:bg-gray-50 transition-colors"
          >
            <!-- Domain info -->
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center space-x-2 flex-1 min-w-0">
                <i :class="getStatusIcon(download.status)" class="text-sm"></i>
                <span class="font-medium text-gray-900 truncate">{{ download.domain }}</span>
                <span class="text-xs text-gray-500">PID: {{ download.pid || '—' }}</span>
              </div>
              <div class="flex items-center space-x-1">
                <button 
                  v-if="download.status === 'running'"
                  @click="pauseDownload(download.id)"
                  class="p-1 text-yellow-600 hover:bg-yellow-50 rounded"
                  title="Пауза"
                >
                  <i class="fas fa-pause text-xs"></i>
                </button>
                <button 
                  v-if="download.status === 'paused'"
                  @click="resumeDownload(download.id)"
                  class="p-1 text-green-600 hover:bg-green-50 rounded"
                  title="Продолжить"
                >
                  <i class="fas fa-play text-xs"></i>
                </button>
                <button 
                  @click="showLogs(download)"
                  class="p-1 text-blue-600 hover:bg-blue-50 rounded"
                  title="Логи"
                >
                  <i class="fas fa-terminal text-xs"></i>
                </button>
                <button 
                  @click="cancelDownload(download.id)"
                  class="p-1 text-red-600 hover:bg-red-50 rounded"
                  title="Отменить"
                >
                  <i class="fas fa-times text-xs"></i>
                </button>
              </div>
            </div>
            
            <!-- Progress bar -->
            <div class="relative h-2 bg-gray-200 rounded-full overflow-hidden mb-1">
              <div 
                class="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
                :class="getProgressClass(download.status)"
                :style="{ width: download.progress + '%' }"
              ></div>
            </div>
            
            <!-- Stats -->
            <div class="flex items-center justify-between text-xs text-gray-500">
              <span>{{ download.progress }}% — {{ download.filesDownloaded || 0 }} файлов</span>
              <span :class="getStatusTextClass(download.status)">{{ getStatusText(download.status) }}</span>
            </div>
            
            <!-- Last log line -->
            <div v-if="download.lastLog" class="mt-1 text-xs text-gray-400 truncate font-mono">
              {{ download.lastLog }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Logs Modal -->
    <Teleport to="body">
      <div v-if="logsModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]" @click.self="logsModal = null">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-3xl mx-4 max-h-[80vh] flex flex-col">
          <div class="flex items-center justify-between p-4 border-b">
            <div class="flex items-center space-x-2">
              <i class="fas fa-terminal text-blue-600"></i>
              <span class="font-bold">Логи: {{ logsModal.domain }}</span>
              <span class="text-xs text-gray-500">PID: {{ logsModal.pid || '—' }}</span>
            </div>
            <button @click="logsModal = null" class="text-gray-400 hover:text-gray-600">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div 
            ref="logsContainer"
            class="flex-1 overflow-y-auto bg-gray-900 p-4 font-mono text-xs text-green-400"
          >
            <div v-for="(line, i) in logsModal.logs" :key="i" class="py-0.5">
              {{ line }}
            </div>
            <div v-if="!logsModal.logs?.length" class="text-gray-500">
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

const props = defineProps({
  folderName: String
})

const emit = defineEmits(['download-complete', 'download-error'])

const isExpanded = ref(false)
const downloads = ref([])
const logsModal = ref(null)
const logsContainer = ref(null)

let pollInterval = null

const activeDownloads = computed(() => downloads.value.filter(d => d.status === 'running'))
const pausedDownloads = computed(() => downloads.value.filter(d => d.status === 'paused'))
const sortedDownloads = computed(() => {
  return [...downloads.value].sort((a, b) => {
    const order = { running: 0, paused: 1, completed: 2, failed: 3 }
    return (order[a.status] || 4) - (order[b.status] || 4)
  })
})

const totalProgress = computed(() => {
  if (activeDownloads.value.length === 0) return 0
  const sum = activeDownloads.value.reduce((acc, d) => acc + (d.progress || 0), 0)
  return Math.round(sum / activeDownloads.value.length)
})

function getStatusIcon(status) {
  switch (status) {
    case 'running': return 'fas fa-spinner fa-spin text-blue-500'
    case 'paused': return 'fas fa-pause text-yellow-500'
    case 'completed': return 'fas fa-check text-green-500'
    case 'failed': return 'fas fa-times text-red-500'
    default: return 'fas fa-clock text-gray-400'
  }
}

function getProgressClass(status) {
  switch (status) {
    case 'running': return 'bg-gradient-to-r from-blue-500 to-purple-500'
    case 'paused': return 'bg-yellow-500'
    case 'completed': return 'bg-green-500'
    case 'failed': return 'bg-red-500'
    default: return 'bg-gray-400'
  }
}

function getStatusText(status) {
  switch (status) {
    case 'running': return 'Загрузка...'
    case 'paused': return 'Пауза'
    case 'completed': return 'Завершено'
    case 'failed': return 'Ошибка'
    default: return 'Ожидание'
  }
}

function getStatusTextClass(status) {
  switch (status) {
    case 'running': return 'text-blue-600'
    case 'paused': return 'text-yellow-600'
    case 'completed': return 'text-green-600'
    case 'failed': return 'text-red-600'
    default: return 'text-gray-500'
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }))
    throw new Error(error.error || error.detail?.error || 'Request failed')
  }
  return response.json()
}

async function addDownload(domain, url, engine = 'wget2') {
  try {
    const data = await fetchJson('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url || `https://${domain}`,
        folder_name: props.folderName,
        engine
      })
    })
    
    if (data.id) {
      downloads.value.push({
        id: data.id,
        domain,
        url: url || `https://${domain}`,
        status: 'running',
        progress: 0,
        pid: data.pid || null,
        filesDownloaded: 0,
        logs: [],
        lastLog: '',
        startedAt: new Date().toISOString()
      })
      
      isExpanded.value = true
      startPolling()
      
      return data.id
    }
  } catch (err) {
    console.error('Error starting download:', err)
    throw err
  }
}

async function pollDownloads() {
  for (const download of downloads.value) {
    if (download.status !== 'running' && download.status !== 'paused') continue
    
    try {
      const data = await fetchJson(`/api/jobs/${download.id}`)
      
      download.progress = data.progress || 0
      download.pid = data.pid || download.pid
      download.filesDownloaded = data.files_downloaded || 0
      
      if (data.output_lines?.length > 0) {
        download.logs = data.output_lines
        download.lastLog = data.output_lines[data.output_lines.length - 1]
      }
      
      if (data.status === 'completed') {
        download.status = 'completed'
        download.progress = 100
        emit('download-complete', download)
      } else if (data.status === 'failed') {
        download.status = 'failed'
        emit('download-error', download)
      }
    } catch (err) {
      console.error(`Error polling download ${download.id}:`, err)
    }
  }
  
  // Stop polling if no active downloads
  if (activeDownloads.value.length === 0) {
    stopPolling()
  }
}

function startPolling() {
  if (pollInterval) return
  pollInterval = setInterval(pollDownloads, 2000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

async function pauseDownload(id) {
  try {
    await fetchJson(`/api/jobs/${id}/pause`, { method: 'POST' })
    const download = downloads.value.find(d => d.id === id)
    if (download) download.status = 'paused'
  } catch (err) {
    console.error('Error pausing download:', err)
  }
}

async function resumeDownload(id) {
  try {
    await fetchJson(`/api/jobs/${id}/resume`, { method: 'POST' })
    const download = downloads.value.find(d => d.id === id)
    if (download) {
      download.status = 'running'
      startPolling()
    }
  } catch (err) {
    console.error('Error resuming download:', err)
  }
}

async function cancelDownload(id) {
  try {
    await fetchJson(`/api/jobs/${id}`, { method: 'DELETE' })
    downloads.value = downloads.value.filter(d => d.id !== id)
  } catch (err) {
    console.error('Error canceling download:', err)
  }
}

function pauseAll() {
  activeDownloads.value.forEach(d => pauseDownload(d.id))
}

function resumeAll() {
  pausedDownloads.value.forEach(d => resumeDownload(d.id))
}

function clearCompleted() {
  downloads.value = downloads.value.filter(d => d.status !== 'completed' && d.status !== 'failed')
}

function showLogs(download) {
  logsModal.value = download
}

// Auto-scroll logs
watch(() => logsModal.value?.logs?.length, () => {
  if (logsContainer.value) {
    setTimeout(() => {
      logsContainer.value.scrollTop = logsContainer.value.scrollHeight
    }, 50)
  }
})

onMounted(() => {
  // Check for existing active jobs
  loadExistingJobs()
})

onUnmounted(() => {
  stopPolling()
})

async function loadExistingJobs() {
  try {
    const data = await fetchJson('/api/jobs')
    const activeJobs = data.filter(j => j.status === 'running' || j.status === 'paused')
    
    for (const job of activeJobs) {
      if (job.folder_name === props.folderName) {
        downloads.value.push({
          id: job.id,
          domain: job.domain || new URL(job.url).hostname,
          url: job.url,
          status: job.status,
          progress: job.progress || 0,
          pid: job.pid || null,
          filesDownloaded: job.files_downloaded || 0,
          logs: job.output_lines || [],
          lastLog: job.output_lines?.[job.output_lines.length - 1] || '',
          startedAt: job.started_at
        })
      }
    }
    
    if (activeDownloads.value.length > 0) {
      startPolling()
    }
  } catch (err) {
    console.error('Error loading existing jobs:', err)
  }
}

// Expose methods for parent component
defineExpose({
  addDownload,
  downloads,
  activeDownloads
})
</script>
