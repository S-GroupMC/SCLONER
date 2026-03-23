import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchJson } from '../utils/fetchApi'
import { config } from '../config'

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
    // Загружаем задачи один раз, polling запускается только если есть активные
    loadJobs()
  }
  
  function startPolling() {
    if (pollInterval) return
    pollInterval = setInterval(() => {
      loadJobs()
    }, config.pollInterval)
  }
  
  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }
  
  async function loadJobs() {
    try {
      const jobsList = await fetchJson('/api/jobs')
      jobsList.forEach(job => {
        jobs.value.set(job.id, job)
      })
      
      // Polling только когда есть активные задачи
      const hasActive = jobsList.some(j => ['running', 'pending', 'paused'].includes(j.status))
      if (hasActive && !pollInterval) {
        startPolling()
      } else if (!hasActive && pollInterval) {
        stopPolling()
      }
    } catch (error) {
      console.error('[Jobs] Error loading jobs:', error)
    }
  }
  
  async function startJob(url, options) {
    try {
      const job = await fetchJson('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, ...options })
      })
      jobs.value.set(job.id, job)
      startPolling()
      return job
    } catch (error) {
      console.error('[Jobs] Error starting job:', error)
      throw error
    }
  }
  
  async function stopJob(jobId) {
    try {
      const job = await fetchJson(`/api/jobs/${jobId}/stop`, {
        method: 'POST'
      })
      jobs.value.set(job.id, job)
    } catch (error) {
      console.error('[Jobs] Error stopping job:', error)
    }
  }
  
  async function pauseJob(jobId) {
    try {
      const job = await fetchJson(`/api/jobs/${jobId}/pause`, {
        method: 'POST'
      })
      jobs.value.set(job.id, job)
    } catch (error) {
      console.error('[Jobs] Error pausing job:', error)
    }
  }
  
  async function resumeJob(jobId) {
    try {
      const job = await fetchJson(`/api/jobs/${jobId}/resume`, {
        method: 'POST'
      })
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
