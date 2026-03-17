<template>
  <div>
    <!-- Секция Артистов из API -->
    <div class="card mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-bold text-gray-900">
          <i class="fas fa-music mr-2 text-purple-600"></i>
          Артисты с лендингами
        </h2>
        <div class="flex items-center space-x-3">
          <!-- Поиск -->
          <div class="relative">
            <input 
              v-model="artistSearch"
              @input="debounceSearch"
              type="text" 
              placeholder="Поиск артиста..."
              class="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent w-64"
            />
            <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
            <button 
              v-if="artistSearch"
              @click="clearSearch"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <i class="fas fa-times"></i>
            </button>
          </div>
          <button @click="loadArtists" class="btn btn-secondary">
            <i class="fas fa-sync-alt mr-2" :class="{ 'fa-spin': artistsLoading }"></i>
            Обновить
          </button>
        </div>
      </div>
      
      <!-- Загрузка -->
      <div v-if="artistsLoading && artists.length === 0" class="text-center py-12">
        <i class="fas fa-spinner fa-spin text-4xl text-purple-400"></i>
        <p class="text-gray-500 mt-4">Загрузка артистов...</p>
      </div>
      
      <!-- Пустой результат -->
      <div v-else-if="artists.length === 0" class="text-center py-12">
        <i class="fas fa-music text-6xl text-gray-300 mb-4"></i>
        <p class="text-gray-500">Артисты не найдены</p>
      </div>
      
      <!-- Сетка артистов -->
      <div v-else>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 mb-6">
          <div 
            v-for="artist in artists" 
            :key="artist.id"
            @click="openArtistLanding(artist)"
            class="bg-white border border-gray-200 rounded-xl overflow-hidden hover:shadow-lg hover:border-purple-300 cursor-pointer transition-all group"
          >
            <div class="aspect-square bg-gradient-to-br from-purple-100 to-pink-100 relative overflow-hidden">
              <img 
                v-if="artist.image_url"
                :src="artist.image_url" 
                :alt="artist.name"
                class="w-full h-full object-cover group-hover:scale-105 transition-transform"
                @error="$event.target.style.display='none'"
              />
              <div v-else class="w-full h-full flex items-center justify-center">
                <i class="fas fa-user text-4xl text-purple-300"></i>
              </div>
              <div class="absolute top-2 right-2">
                <span class="bg-green-500 text-white text-xs px-2 py-1 rounded-full">
                  <i class="fas fa-link mr-1"></i>Лендинг
                </span>
              </div>
            </div>
            <div class="p-3">
              <h3 class="font-semibold text-gray-900 truncate group-hover:text-purple-600">
                {{ artist.name }}
              </h3>
              <p v-if="artist.genre" class="text-xs text-gray-500 truncate">
                {{ artist.genre }}
              </p>
            </div>
          </div>
        </div>
        
        <!-- Пагинация -->
        <div class="flex items-center justify-between border-t border-gray-200 pt-4">
          <div class="text-sm text-gray-600">
            Показано {{ artists.length }} из {{ artistsTotal }}
          </div>
          <div class="flex items-center space-x-2">
            <button 
              @click="prevPage"
              :disabled="artistsPage <= 1"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              <i class="fas fa-chevron-left mr-1"></i>Назад
            </button>
            <span class="px-3 py-1.5 text-sm text-gray-600">
              Страница {{ artistsPage }} из {{ artistsTotalPages }}
            </span>
            <button 
              @click="nextPage"
              :disabled="artistsPage >= artistsTotalPages"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Вперёд<i class="fas fa-chevron-right ml-1"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <div class="card">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold text-gray-900">
          <i class="fas fa-globe mr-2 text-blue-600"></i>
          Скачанные сайты
        </h2>
        <button @click="refresh" class="btn btn-secondary">
          <i class="fas fa-sync-alt mr-2" :class="{ 'fa-spin': loading }"></i>
          Обновить
        </button>
      </div>
      
      <div v-if="loading" class="text-center py-16">
        <i class="fas fa-spinner fa-spin text-4xl text-gray-400"></i>
        <p class="text-gray-500 mt-4">Загрузка...</p>
      </div>
      
      <div v-else-if="allFolders.length === 0" class="text-center py-16">
        <i class="fas fa-globe text-6xl text-gray-300 mb-4"></i>
        <p class="text-gray-500">Нет скачанных сайтов</p>
        <router-link to="/download" class="btn btn-primary mt-4 inline-block">
          <i class="fas fa-download mr-2"></i>
          Скачать первый сайт
        </router-link>
      </div>
      
      <div v-else class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-gray-50 border-b-2 border-gray-200">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Домен
              </th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Статус
              </th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Файлов
              </th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Размер
              </th>
              <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Движок
              </th>
              <th class="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Действия
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr 
              v-for="folder in allFolders" 
              :key="folder.folder_name"
              @click="goToSiteDetails(folder.folder_name)"
              class="hover:bg-blue-50 cursor-pointer transition-colors group"
            >
              <td class="px-4 py-3">
                <div class="flex items-center space-x-3">
                  <i class="fas fa-globe text-blue-600 group-hover:text-blue-700"></i>
                  <span class="font-medium text-gray-900 group-hover:text-blue-600">
                    {{ folder.domain }}
                  </span>
                </div>
              </td>
              
              <td class="px-4 py-3">
                <span 
                  v-if="folder.is_active || folder.status === 'downloading'"
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 animate-pulse"
                >
                  <i class="fas fa-spinner fa-spin mr-1"></i>
                  Скачивается
                </span>
                <span 
                  v-else-if="folder.status === 'prepared'"
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"
                >
                  <i class="fas fa-folder-open mr-1"></i>
                  Подготовлено
                </span>
                <span 
                  v-else-if="folder.status === 'scanned'"
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800"
                >
                  <i class="fas fa-search mr-1"></i>
                  Проанализировано
                </span>
                <span 
                  v-else-if="folder.job?.status === 'completed'"
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
                >
                  <i class="fas fa-check mr-1"></i>
                  Завершено
                </span>
                <span 
                  v-else-if="folder.job?.status === 'failed'"
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"
                >
                  <i class="fas fa-times mr-1"></i>
                  Ошибка
                </span>
                <span 
                  v-else
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
                >
                  <i class="fas fa-check-circle mr-1"></i>
                  Скачано
                </span>
              </td>
              
              <td class="px-4 py-3 text-sm text-gray-900">
                {{ folder.files || 0 }}
              </td>
              
              <td class="px-4 py-3 text-sm text-gray-900">
                {{ folder.size || '0 B' }}
              </td>
              
              <td class="px-4 py-3">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                  <i class="fas fa-cog mr-1"></i>
                  {{ folder.engine || 'wget2' }}
                </span>
              </td>
              
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end space-x-2">
                  <button 
                    @click.stop="goToSiteDetails(folder.folder_name)"
                    class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    title="Подробнее"
                  >
                    <i class="fas fa-eye mr-1"></i>
                    Открыть
                  </button>
                  <button 
                    @click.stop="checkChanges(folder.folder_name)"
                    class="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    title="Проверить изменения"
                  >
                    <i class="fas fa-sync-alt mr-1"></i>
                    Проверить
                  </button>
                  <button 
                    @click.stop="deleteFolder(folder.folder_name)"
                    class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                    title="Удалить"
                  >
                    <i class="fas fa-trash mr-1"></i>
                    Удалить
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useLandingsStore } from '../stores/landings'
import ActiveDownloads from '../components/ActiveDownloads.vue'

const router = useRouter()
const landingsStore = useLandingsStore()

const landings = computed(() => landingsStore.landings)
const loading = computed(() => landingsStore.loading)

// Артисты из API
const ARTISTS_API = 'https://adminzone.space/api/v1/public/artists'
const API_KEY = 'sk-stickets-public-2026'
const PER_PAGE = 20

const artists = ref([])
const artistsLoading = ref(false)
const artistsTotal = ref(0)
const artistsPage = ref(1)
const artistSearch = ref('')
let searchTimeout = null

const artistsTotalPages = computed(() => Math.ceil(artistsTotal.value / PER_PAGE) || 1)

async function loadArtists() {
  artistsLoading.value = true
  try {
    const params = new URLSearchParams({
      has_landing: 'true',
      limit: PER_PAGE.toString(),
      offset: ((artistsPage.value - 1) * PER_PAGE).toString()
    })
    
    if (artistSearch.value.trim()) {
      params.append('search', artistSearch.value.trim())
    }
    
    const response = await fetch(`${ARTISTS_API}?${params}`, {
      headers: { 'X-API-Key': API_KEY }
    })
    
    if (!response.ok) throw new Error('Ошибка загрузки артистов')
    
    const data = await response.json()
    artists.value = data.artists || data.data || data || []
    artistsTotal.value = data.total || data.count || artists.value.length
  } catch (err) {
    console.error('Ошибка загрузки артистов:', err)
    artists.value = []
  } finally {
    artistsLoading.value = false
  }
}

function debounceSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    artistsPage.value = 1
    loadArtists()
  }, 400)
}

function clearSearch() {
  artistSearch.value = ''
  artistsPage.value = 1
  loadArtists()
}

function prevPage() {
  if (artistsPage.value > 1) {
    artistsPage.value--
    loadArtists()
  }
}

function nextPage() {
  if (artistsPage.value < artistsTotalPages.value) {
    artistsPage.value++
    loadArtists()
  }
}

function openArtistLanding(artist) {
  if (artist.landing_url) {
    window.open(artist.landing_url, '_blank')
  } else if (artist.url) {
    window.open(artist.url, '_blank')
  }
}

const allFolders = computed(() => {
  const folders = []
  for (const domain of landings.value) {
    folders.push(...domain.folders)
  }
  return folders
})

function goToSiteDetails(folderName) {
  router.push(`/site/${folderName}`)
}

async function refresh() {
  await landingsStore.loadLandings()
}

async function checkChanges(folderName) {
  try {
    const result = await landingsStore.checkChanges(folderName)
    
    let message = `Проверка изменений для ${folderName}\n\n`
    message += `URL: ${result.url}\n`
    message += `Проверено: ${new Date(result.checked_at).toLocaleString('ru-RU')}\n\n`
    
    if (result.has_changes) {
      message += '🔴 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ!\n\n'
      if (result.title_changed) {
        message += `Заголовок изменён:\n`
        message += `  Локально: "${result.local_title}"\n`
        message += `  Онлайн: "${result.online_title}"\n\n`
      }
      message += 'Рекомендуется перескачать сайт.'
    } else {
      message += '✅ Изменений не обнаружено\n\nЛокальная версия актуальна.'
    }
    
    alert(message)
  } catch (error) {
    alert('Ошибка проверки: ' + error.message)
  }
}

async function deleteFolder(folderName) {
  if (!confirm(`Удалить "${folderName}"? Это действие нельзя отменить.`)) {
    return
  }
  
  try {
    await landingsStore.deleteFolder(folderName)
  } catch (error) {
    alert('Ошибка удаления: ' + error.message)
  }
}

onMounted(() => {
  loadArtists()
  landingsStore.loadLandings()
})
</script>
