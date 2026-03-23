import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchJson } from '../utils/fetchApi'

export const useLandingsStore = defineStore('landings', () => {
  const landings = ref([])
  const loading = ref(false)
  
  async function loadLandings() {
    loading.value = true
    try {
      landings.value = await fetchJson('/api/landings')
    } catch (error) {
      console.error('[Landings] Error loading:', error)
    } finally {
      loading.value = false
    }
  }
  
  async function deleteFolder(folderName) {
    try {
      await fetchJson(`/api/downloads/${encodeURIComponent(folderName)}`, {
        method: 'DELETE'
      })
      await loadLandings()
    } catch (error) {
      console.error('[Landings] Error deleting:', error)
      throw error
    }
  }
  
  async function checkChanges(folderName) {
    try {
      return await fetchJson(`/api/check-changes/${encodeURIComponent(folderName)}`)
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
