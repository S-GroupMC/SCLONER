import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLandingsStore = defineStore('landings', () => {
  const landings = ref([])
  const loading = ref(false)
  
  async function loadLandings() {
    loading.value = true
    try {
      const response = await fetch('/api/landings')
      landings.value = await response.json()
    } catch (error) {
      console.error('[Landings] Error loading:', error)
    } finally {
      loading.value = false
    }
  }
  
  async function deleteFolder(folderName) {
    try {
      const response = await fetch(`/api/downloads/${encodeURIComponent(folderName)}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        await loadLandings()
      }
    } catch (error) {
      console.error('[Landings] Error deleting:', error)
      throw error
    }
  }
  
  async function checkChanges(folderName) {
    try {
      const response = await fetch(`/api/check-changes/${encodeURIComponent(folderName)}`)
      return await response.json()
    } catch (error) {
      console.error('[Landings] Error checking changes:', error)
      throw error
    }
  }
  
  return {
    landings,
    loading,
    loadLandings,
    deleteFolder,
    checkChanges
  }
})
