import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useJobsStore = defineStore('jobs', () => {
  const jobs = ref(new Map())
  
  const activeJobs = computed(() => {
    return Array.from(jobs.value.values())
      .filter(j => ['running', 'pending', 'paused'].includes(j.status))
  })
  
  const completedJobs = computed(() => {
    return Array.from(jobs.value.values())
      .filter(j => ['completed', 'failed', 'stopped'].includes(j.status))
  })
  
  let pollInterval = null
  
  function initSocket() {
    // Загружаем задачи и запускаем периодическое обновление
    loadJobs()
    startPolling()
  }
  
  function startPolling() {
    if (pollInterval) return
    pollInterval = setInterval(() => {
      loadJobs()
    }, 3000) // Обновляем каждые 3 секунды
  }
  
  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }
  
  async function loadJobs() {
    try {
      const response = await fetch('/api/jobs')
      const jobsList = await response.json()
      jobsList.forEach(job => {
        jobs.value.set(job.id, job)
      })
    } catch (error) {
      console.error('[Jobs] Error loading jobs:', error)
    }
  }
  
  async function startJob(url, options) {
    try {
      const response = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, ...options })
      })
      const job = await response.json()
      jobs.value.set(job.id, job)
      return job
    } catch (error) {
      console.error('[Jobs] Error starting job:', error)
      throw error
    }
  }
  
  async function stopJob(jobId) {
    try {
      const response = await fetch(`/api/jobs/${jobId}/stop`, {
        method: 'POST'
      })
      const job = await response.json()
      jobs.value.set(job.id, job)
    } catch (error) {
      console.error('[Jobs] Error stopping job:', error)
    }
  }
  
  async function pauseJob(jobId) {
    try {
      const response = await fetch(`/api/jobs/${jobId}/pause`, {
        method: 'POST'
      })
      const job = await response.json()
      jobs.value.set(job.id, job)
    } catch (error) {
      console.error('[Jobs] Error pausing job:', error)
    }
  }
  
  async function resumeJob(jobId) {
    try {
      const response = await fetch(`/api/jobs/${jobId}/resume`, {
        method: 'POST'
      })
      const job = await response.json()
      jobs.value.set(job.id, job)
    } catch (error) {
      console.error('[Jobs] Error resuming job:', error)
    }
  }
  
  function getJob(jobId) {
    return jobs.value.get(jobId)
  }
  
  return {
    jobs,
    activeJobs,
    completedJobs,
    initSocket,
    loadJobs,
    startJob,
    stopJob,
    pauseJob,
    resumeJob,
    getJob,
    startPolling,
    stopPolling
  }
})
