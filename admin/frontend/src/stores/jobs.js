import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { io } from 'socket.io-client'

export const useJobsStore = defineStore('jobs', () => {
  const jobs = ref(new Map())
  const socket = ref(null)
  
  const activeJobs = computed(() => {
    return Array.from(jobs.value.values())
      .filter(j => ['running', 'pending', 'paused'].includes(j.status))
  })
  
  const completedJobs = computed(() => {
    return Array.from(jobs.value.values())
      .filter(j => ['completed', 'failed', 'stopped'].includes(j.status))
  })
  
  function initSocket() {
    const socketUrl = window.location.hostname === 'localhost'
      ? 'http://localhost:8888'
      : window.location.origin
    socket.value = io(socketUrl, {
      transports: ['websocket', 'polling']
    })
    
    socket.value.on('connect', () => {
      console.log('[Socket] Connected')
      loadJobs()
    })
    
    socket.value.on('job_update', (data) => {
      console.log('[Socket] Job update:', data.id)
      jobs.value.set(data.id, data)
    })
    
    socket.value.on('disconnect', () => {
      console.log('[Socket] Disconnected')
    })
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
    getJob
  }
})
