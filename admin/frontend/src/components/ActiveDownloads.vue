<template>
  <div v-if="activeJobs.length > 0" class="mb-6">
    <div class="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl shadow-lg p-4">
      <h3 class="text-white font-semibold text-sm mb-3 flex items-center">
        <i class="fas fa-download mr-2 animate-pulse"></i>
        Активные загрузки
        <span class="ml-2 px-2 py-0.5 bg-white/20 rounded-full text-xs">
          ({{ activeJobs.length }})
        </span>
      </h3>
      
      <div class="space-y-2">
        <div 
          v-for="job in activeJobs" 
          :key="job.id"
          class="bg-white/10 backdrop-blur rounded-lg p-3 border border-white/20"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center space-x-2 flex-1 min-w-0">
              <i :class="getStatusIcon(job.status)" class="text-white text-sm"></i>
              <span class="text-white font-medium text-sm truncate">{{ job.url }}</span>
              <span :class="getStatusBadgeClass(job.status)" class="px-2 py-1 text-xs rounded-full ml-2">
                {{ getStatusText(job.status) }}
              </span>
            </div>
            
            <div class="flex items-center space-x-1 ml-2">
              <button 
                v-if="job.status === 'paused'"
                @click="resumeJob(job.id)"
                class="px-2 py-1 bg-green-500/80 text-white rounded hover:bg-green-600 text-xs"
                title="Продолжить"
              >
                <i class="fas fa-play"></i>
              </button>
              <button 
                v-else
                @click="pauseJob(job.id)"
                class="px-2 py-1 bg-blue-500/80 text-white rounded hover:bg-blue-600 text-xs"
                title="Пауза"
              >
                <i class="fas fa-pause"></i>
              </button>
              <button 
                @click="stopJob(job.id)"
                class="px-2 py-1 bg-red-500/80 text-white rounded hover:bg-red-600 text-xs"
                title="Стоп"
              >
                <i class="fas fa-stop"></i>
              </button>
              <button 
                @click="showLog(job)"
                class="px-2 py-1 bg-white/20 text-white rounded hover:bg-white/30 text-xs"
                title="Лог"
              >
                <i class="fas fa-terminal"></i>
              </button>
            </div>
          </div>
          
          <div class="flex items-center space-x-3 mb-2 text-xs">
            <span class="text-white/80">
              <i class="fas fa-file mr-1"></i>{{ job.files_downloaded }} файлов
            </span>
            <span class="text-white/80">
              <i class="fas fa-hdd mr-1"></i>{{ job.total_size }}
            </span>
            <span class="text-white/80">
              <i class="fas fa-cog mr-1"></i>{{ job.engine || 'wget2' }}
            </span>
          </div>
          
          <div class="w-full bg-white/20 rounded-full h-2 mb-2">
            <div 
              class="bg-gradient-to-r from-green-400 to-blue-500 h-2 rounded-full transition-all duration-300"
              :style="{ width: getProgress(job) + '%' }"
            ></div>
          </div>
          
          <div class="text-white/60 text-xs truncate font-mono bg-black/20 rounded px-2 py-1">
            {{ getLastLogLine(job) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useJobsStore } from '../stores/jobs'

const jobsStore = useJobsStore()

const activeJobs = computed(() => jobsStore.activeJobs)

function getStatusIcon(status) {
  const icons = {
    'running': 'fas fa-spinner fa-spin',
    'pending': 'fas fa-clock',
    'paused': 'fas fa-pause'
  }
  return icons[status] || 'fas fa-spinner fa-spin'
}

function getStatusBadgeClass(status) {
  const classes = {
    'running': 'bg-green-500/50 text-white animate-pulse',
    'pending': 'bg-yellow-500/50 text-white',
    'paused': 'bg-blue-500/50 text-white'
  }
  return classes[status] || 'bg-gray-500/50 text-white'
}

function getStatusText(status) {
  const texts = {
    'running': 'СКАЧИВАНИЕ',
    'pending': 'ОЖИДАНИЕ',
    'paused': 'ПАУЗА'
  }
  return texts[status] || status.toUpperCase()
}

function getLastLogLine(job) {
  if (job.output_lines && job.output_lines.length > 0) {
    return job.output_lines[job.output_lines.length - 1]
  }
  return 'Инициализация...'
}

function pauseJob(jobId) {
  jobsStore.pauseJob(jobId)
}

function resumeJob(jobId) {
  jobsStore.resumeJob(jobId)
}

function stopJob(jobId) {
  if (confirm('Остановить загрузку?')) {
    jobsStore.stopJob(jobId)
  }
}

function getProgress(job) {
  if (job.progress !== undefined && job.progress !== null) {
    return Math.min(Math.max(job.progress, 0), 100)
  }
  if (job.status === 'running') {
    return Math.min((job.files_downloaded || 0) / Math.max(job.total_files || 100, 1) * 100, 95)
  }
  return 0
}

function showLog(job) {
  let logText = `Log: ${job.url}\n\n`
  if (job.output_lines && job.output_lines.length > 0) {
    const lastLines = job.output_lines.slice(-30)
    logText += lastLines.join('\n')
  } else {
    logText += 'Log pust'
  }
  alert(logText)
}
</script>
