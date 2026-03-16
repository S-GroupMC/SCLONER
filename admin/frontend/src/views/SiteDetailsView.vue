<template>
  <div class="max-w-7xl mx-auto">
    <div v-if="loading" class="flex items-center justify-center py-20">
      <i class="fas fa-spinner fa-spin text-4xl text-gray-400"></i>
    </div>
    
    <div v-else-if="error" class="card">
      <div class="text-center py-10">
        <i class="fas fa-exclamation-triangle text-6xl text-red-400 mb-4"></i>
        <p class="text-red-600 text-lg">{{ error }}</p>
        <router-link to="/landings" class="btn btn-primary mt-4 inline-block">
          <i class="fas fa-arrow-left mr-2"></i>Назад к списку
        </router-link>
      </div>
    </div>
    
    <div v-else class="space-y-4">
      <!-- Шапка -->
      <div class="card">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <router-link to="/landings" class="text-gray-600 hover:text-gray-900">
              <i class="fas fa-arrow-left text-xl"></i>
            </router-link>
            <div>
              <h1 class="text-2xl font-bold text-gray-900">{{ siteData.domain }}</h1>
              <p class="text-sm text-gray-500">{{ siteData.folder_name }}</p>
            </div>
          </div>
          
          <div class="flex space-x-2">
            <button @click="openInBrowser" class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg text-white bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 shadow-md hover:shadow-lg transition-all">
              <i class="fas fa-external-link-alt mr-2"></i>Открыть
            </button>
            <button @click="redownloadSite" class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg text-white bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-md hover:shadow-lg transition-all">
              <i class="fas fa-download mr-2"></i>Перекачать
            </button>
            <button @click="openFolder" class="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 shadow-sm hover:shadow transition-all">
              <i class="fas fa-folder-open mr-2"></i>Папка
            </button>
            <button @click="checkChanges" class="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg text-purple-700 bg-purple-50 border border-purple-200 hover:bg-purple-100 shadow-sm hover:shadow transition-all">
              <i class="fas fa-sync-alt mr-2"></i>Проверить
            </button>
            <button @click="deleteSite" class="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg text-red-700 bg-red-50 border border-red-200 hover:bg-red-100 shadow-sm hover:shadow transition-all">
              <i class="fas fa-trash mr-2"></i>Удалить
            </button>
          </div>
        </div>
      </div>
      
      <!-- Активная загрузка (перекачивание) -->
      <div v-if="activeJob" class="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl shadow-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-white font-semibold text-sm flex items-center">
            <i class="fas fa-download mr-2 animate-pulse"></i>
            Перекачивание сайта
          </h3>
          <div class="flex items-center space-x-2">
            <button 
              @click="stopRedownload"
              class="px-3 py-1 bg-red-500/80 text-white rounded hover:bg-red-600 text-xs"
            >
              <i class="fas fa-stop mr-1"></i>Остановить
            </button>
          </div>
        </div>
        
        <div class="flex items-center space-x-4 mb-3 text-sm text-white/80">
          <span><i class="fas fa-globe mr-1"></i>{{ siteData.domain }}</span>
          <span><i class="fas fa-file mr-1"></i>{{ activeJob.files || 0 }} файлов</span>
          <span><i class="fas fa-hdd mr-1"></i>{{ activeJob.size || '0 B' }}</span>
        </div>
        
        <div class="w-full bg-white/20 rounded-full h-3 mb-2">
          <div 
            class="bg-gradient-to-r from-green-400 to-blue-500 h-3 rounded-full transition-all duration-300 flex items-center justify-end pr-2"
            :style="{ width: Math.max(activeJob.progress || 0, 5) + '%' }"
          >
            <span class="text-xs text-white font-bold">{{ activeJob.progress || 0 }}%</span>
          </div>
        </div>
        
        <div class="text-white/60 text-xs truncate font-mono bg-black/20 rounded px-2 py-1">
          {{ activeJob.lastLog || 'Инициализация...' }}
        </div>
      </div>
      
      <!-- Основная информация с превью -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- Левая колонка: Превью -->
        <div class="card">
          <h3 class="text-sm font-semibold text-gray-700 mb-3">Превью сайта</h3>
          <div class="aspect-video bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg overflow-hidden shadow-lg mb-3 relative">
            <img 
              v-if="thumbnailUrl && !thumbnailError"
              :src="thumbnailUrl" 
              class="w-full h-full object-cover"
              @error="thumbnailError = true"
            />
            <iframe 
              v-else-if="previewUrl"
              :src="previewUrl" 
              class="w-full h-full border-0"
              sandbox="allow-same-origin"
            ></iframe>
            <div v-else class="w-full h-full flex flex-col items-center justify-center text-white">
              <i class="fas fa-image text-5xl opacity-40 mb-2"></i>
              <span class="text-sm opacity-60">Нет превью</span>
            </div>
          </div>
          <div class="flex space-x-2">
            <button @click="openInBrowser" class="flex-1 inline-flex items-center justify-center px-3 py-2 text-sm font-medium rounded-lg text-white bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 shadow-sm transition-all">
              <i class="fas fa-external-link-alt mr-2"></i>Открыть
            </button>
            <button @click="generateThumbnail" :disabled="generatingThumb" class="inline-flex items-center justify-center px-3 py-2 text-sm font-medium rounded-lg text-purple-700 bg-purple-50 border border-purple-200 hover:bg-purple-100 shadow-sm transition-all disabled:opacity-50">
              <i class="fas mr-1" :class="generatingThumb ? 'fa-spinner fa-spin' : 'fa-camera'"></i>
              {{ generatingThumb ? '' : 'Скрин' }}
            </button>
          </div>
        </div>
        
        <!-- Правая колонка: Информация -->
        <div class="lg:col-span-2 space-y-4">
          <!-- Статистика -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="card bg-blue-50">
              <div class="text-xs text-blue-600 mb-1">Статус</div>
              <span :class="statusBadgeClass" class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium">
                <i :class="statusIcon" class="mr-1"></i>
                {{ statusText }}
              </span>
            </div>
            
            <div class="card bg-green-50">
              <div class="text-xs text-green-600 mb-1">Файлов</div>
              <div class="text-xl font-bold text-gray-900">{{ siteData.files || 0 }}</div>
            </div>
            
            <div class="card bg-purple-50">
              <div class="text-xs text-purple-600 mb-1">Размер</div>
              <div class="text-xl font-bold text-gray-900">{{ siteData.size || '0 B' }}</div>
            </div>
            
            <div class="card bg-orange-50">
              <div class="text-xs text-orange-600 mb-1">Движок</div>
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                <i class="fas fa-cog mr-1"></i>
                {{ siteData.engine || 'wget2' }}
              </span>
            </div>
          </div>
          
          <!-- Информация -->
          <div class="card">
            <h3 class="text-sm font-semibold text-gray-700 mb-3">Основная информация</h3>
            <div class="space-y-2 text-sm">
              <div v-if="siteData.url" class="flex items-start">
                <span class="text-gray-500 w-32 flex-shrink-0">URL:</span>
                <a :href="siteData.url" target="_blank" class="text-blue-600 hover:underline flex items-center flex-1">
                  {{ siteData.url }}
                  <i class="fas fa-external-link-alt ml-2 text-xs"></i>
                </a>
              </div>
              
              <div v-if="siteData.path" class="flex items-start">
                <span class="text-gray-500 w-32 flex-shrink-0">Путь:</span>
                <span class="text-gray-900 font-mono text-xs flex-1">{{ siteData.path }}</span>
              </div>
              
              <div v-if="siteData.date" class="flex items-start">
                <span class="text-gray-500 w-32 flex-shrink-0">Скачано:</span>
                <span class="text-gray-900">{{ siteData.date }}</span>
              </div>
            </div>
          </div>
          
          <!-- Статус обновлений -->
          <div class="card" :class="changesStatus.bgClass">
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-sm font-semibold text-gray-700 flex items-center">
                <i :class="changesStatus.icon" class="mr-2"></i>
                Статус обновлений
              </h3>
              <button @click="checkChanges" class="text-xs text-blue-600 hover:text-blue-700">
                <i class="fas fa-sync-alt mr-1"></i>Проверить сейчас
              </button>
            </div>
            
            <div v-if="lastCheck" class="text-sm space-y-1">
              <div class="flex justify-between">
                <span class="text-gray-600">Последняя проверка:</span>
                <span class="text-gray-900 font-medium">{{ lastCheck.date }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Результат:</span>
                <span :class="changesStatus.textClass" class="font-medium">
                  {{ changesStatus.text }}
                </span>
              </div>
            </div>
            <div v-else class="text-sm text-gray-500">
              Проверка не выполнялась
            </div>
          </div>
        </div>
      </div>
      
      <!-- Табы навигации -->
      <div class="card !pb-0">
        <div class="flex border-b border-gray-200 -mx-6 px-6">
          <button 
            v-if="subdomains.length > 0"
            @click="activeTab = 'subdomains'"
            class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center space-x-2"
            :class="activeTab === 'subdomains' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
          >
            <i class="fas fa-sitemap"></i>
            <span>Поддомены</span>
            <span class="ml-1 px-1.5 py-0.5 text-xs rounded-full" :class="activeTab === 'subdomains' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'">{{ subdomains.length }}</span>
          </button>
          <button 
            @click="activeTab = 'files'"
            class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center space-x-2"
            :class="activeTab === 'files' ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
          >
            <i class="fas fa-folder-tree"></i>
            <span>Файлы</span>
            <span v-if="fileTreeStats" class="ml-1 px-1.5 py-0.5 text-xs rounded-full" :class="activeTab === 'files' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'">{{ fileTreeStats.total_files }}</span>
          </button>
          <button 
            @click="activeTab = 'changes'"
            class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center space-x-2"
            :class="activeTab === 'changes' ? 'border-red-600 text-red-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
          >
            <i class="fas fa-exchange-alt"></i>
            <span>Изменения</span>
            <span v-if="changesData && changesData.changed > 0" class="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-red-100 text-red-700">{{ changesData.changed }}</span>
          </button>
          <button 
            @click="activeTab = 'info'"
            class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center space-x-2"
            :class="activeTab === 'info' ? 'border-purple-600 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
          >
            <i class="fas fa-info-circle"></i>
            <span>Инфо</span>
          </button>
        </div>
      </div>
      
      <!-- ТАБ: Поддомены -->
      <div v-show="activeTab === 'subdomains'" v-if="subdomains.length > 0" class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold text-gray-900 flex items-center">
            <i class="fas fa-sitemap mr-2 text-blue-600"></i>
            Поддомены ({{ filteredSubdomains.length }}<span v-if="filteredSubdomains.length !== subdomains.length">/{{ subdomains.length }}</span>)
            <span v-if="excludedCount > 0" class="ml-2 text-xs font-normal text-red-500">
              {{ excludedCount }} исключено
            </span>
          </h2>
          <div class="flex items-center space-x-3">
            <label class="inline-flex items-center text-xs cursor-pointer">
              <input type="checkbox" v-model="onlyRelevant" class="w-4 h-4 text-blue-600 rounded mr-1.5">
              <span class="text-gray-600">Только свои + CDN</span>
            </label>
            <select v-model="sortBy" class="text-xs border border-gray-300 rounded px-2 py-1 bg-white">
              <option value="name">По имени</option>
              <option value="tag">По тегу</option>
              <option value="files">По файлам</option>
              <option value="size">По размеру</option>
            </select>
          </div>
        </div>
        
        <!-- Фильтр по тегам -->
        <div class="flex flex-wrap gap-2 mb-3">
          <button 
            @click="filterTag = ''"
            :class="filterTag === '' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
            class="px-2 py-1 text-xs font-medium rounded transition-colors"
          >Все</button>
          <button 
            v-for="t in availableTags" :key="t.id"
            @click="filterTag = t.id"
            :class="filterTag === t.id ? t.activeClass : t.inactiveClass"
            class="px-2 py-1 text-xs font-medium rounded transition-colors inline-flex items-center"
          >
            <i :class="t.icon" class="mr-1"></i>{{ t.label }}
            <span class="ml-1 opacity-70">({{ tagCounts[t.id] || 0 }})</span>
          </button>
        </div>
        
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead class="bg-gray-50 border-b-2 border-gray-200">
              <tr>
                <th class="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider w-10">
                  <i class="fas fa-download text-xs" title="Скачивать"></i>
                </th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Поддомен</th>
                <th class="px-3 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Тег</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Статус</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Файлов</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Размер</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Страниц</th>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Дата</th>
                <th class="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">Действия</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr 
                v-for="subdomain in filteredSubdomains" 
                :key="subdomain.name"
                :class="subdomain.excluded ? 'bg-red-50/50 opacity-60' : 'hover:bg-blue-50'"
                class="transition-colors"
              >
                <td class="px-3 py-3 text-center">
                  <input 
                    type="checkbox"
                    :checked="!subdomain.excluded"
                    @change="toggleSubdomainExclude(subdomain)"
                    class="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500 cursor-pointer"
                    :title="subdomain.excluded ? 'Включить в скачивание' : 'Исключить из скачивания'"
                  />
                </td>
                
                <td class="px-4 py-3">
                  <div class="flex items-center space-x-2">
                    <i class="fas fa-globe text-sm" :class="subdomain.excluded ? 'text-gray-400' : 'text-blue-600'"></i>
                    <span class="text-sm font-medium" :class="subdomain.excluded ? 'text-gray-400 line-through' : 'text-gray-900'">
                      {{ subdomain.name }}
                    </span>
                  </div>
                </td>
                
                <td class="px-3 py-3">
                  <select
                    :value="subdomain.tag"
                    @change="setSubdomainTag(subdomain, $event.target.value)"
                    class="text-xs border border-gray-200 rounded px-1 py-0.5 bg-white cursor-pointer w-24"
                    :class="getTagInfo(subdomain.tag).selectClass"
                  >
                    <option value="">--</option>
                    <option v-for="t in availableTags" :key="t.id" :value="t.id">{{ t.label }}</option>
                  </select>
                </td>
                
                <td class="px-4 py-3">
                  <span 
                    v-if="subdomain.excluded"
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"
                  >
                    <i class="fas fa-ban mr-1"></i>Исключён
                  </span>
                  <span 
                    v-else-if="subdomain.hasIndex"
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
                  >
                    <i class="fas fa-check mr-1"></i>Скачано
                  </span>
                  <span 
                    v-else-if="subdomain.files > 0"
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"
                  >
                    <i class="fas fa-exclamation mr-1"></i>Частично
                  </span>
                  <span 
                    v-else
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                  >
                    <i class="fas fa-minus mr-1"></i>Пусто
                  </span>
                </td>
                
                <td class="px-4 py-3 text-sm text-gray-900">{{ subdomain.files }}</td>
                <td class="px-4 py-3 text-sm text-gray-900">{{ subdomain.size }}</td>
                <td class="px-4 py-3 text-sm text-gray-900">{{ subdomain.pages.length }}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{{ subdomain.date }}</td>
                
                <td class="px-4 py-3 text-right">
                  <div class="flex items-center justify-end space-x-1 flex-wrap gap-y-1">
                    <button 
                      v-if="!subdomain.hasIndex && !subdomain.excluded"
                      @click="downloadSubdomain(subdomain)"
                      class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-white bg-green-600 hover:bg-green-700"
                      title="Скачать поддомен"
                    >
                      <i class="fas fa-download mr-1"></i>Скачать
                    </button>
                    <button 
                      v-if="subdomain.hasIndex && !subdomain.excluded"
                      @click="redownloadSubdomain(subdomain)"
                      class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-white bg-orange-500 hover:bg-orange-600"
                      title="Перескачать поддомен"
                    >
                      <i class="fas fa-sync-alt mr-1"></i>Перекачать
                    </button>
                    <button 
                      v-if="subdomain.hasIndex && !subdomain.excluded"
                      @click="checkSubdomainChanges(subdomain)"
                      class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-white bg-purple-600 hover:bg-purple-700"
                      title="Проверить изменения"
                    >
                      <i class="fas fa-search mr-1"></i>Проверить
                    </button>
                    <button 
                      v-if="subdomain.hasIndex && !subdomain.excluded"
                      @click="openSubdomain(subdomain)"
                      class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-white bg-blue-600 hover:bg-blue-700"
                      title="Открыть в браузере"
                    >
                      <i class="fas fa-external-link-alt mr-1"></i>Открыть
                    </button>
                    <button 
                      v-if="!subdomain.excluded"
                      @click="openSubdomainFolder(subdomain)"
                      class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-gray-700 bg-gray-100 hover:bg-gray-200"
                      title="Открыть папку"
                    >
                      <i class="fas fa-folder-open mr-1"></i>Папка
                    </button>
                    <button 
                      v-if="subdomain.files > 0 && !subdomain.excluded"
                      @click="goToSubdomainFiles(subdomain)"
                      class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-yellow-700 bg-yellow-100 hover:bg-yellow-200"
                      title="Перейти к файлам поддомена"
                    >
                      <i class="fas fa-folder-tree mr-1"></i>Файлы
                    </button>
                    <a 
                      :href="'https://' + subdomain.name"
                      target="_blank"
                      class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-green-700 bg-green-100 hover:bg-green-200"
                      title="Оригинальный сайт"
                    >
                      <i class="fas fa-globe mr-1"></i>Онлайн
                    </a>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- ТАБ: Файлы сайта -->
      <div v-show="activeTab === 'files'" class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold text-gray-900 flex items-center">
            <i class="fas fa-folder-tree mr-2 text-green-600"></i>
            Файлы сайта
            <span v-if="fileTreeStats" class="ml-2 text-sm font-normal text-gray-500">
              ({{ fileTreeStats.total_files }} файлов, {{ fileTreeStats.total_size_formatted }})
            </span>
          </h2>
          <div class="flex items-center space-x-2">
            <button @click="checkIntegrity" :disabled="integrityLoading" class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-white bg-red-600 hover:bg-red-700 disabled:opacity-50" title="Проверить целостность CSS/JS/чанков">
              <i class="fas mr-1" :class="integrityLoading ? 'fa-spinner fa-spin' : 'fa-stethoscope'"></i>Целостность
            </button>
            <button @click="loadFileTree" class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-gray-700 bg-gray-100 hover:bg-gray-200" title="Обновить">
              <i class="fas fa-sync-alt mr-1"></i>Обновить
            </button>
            <button @click="toggleAllFolders" class="inline-flex items-center px-2 py-1 text-xs font-medium rounded text-gray-700 bg-gray-100 hover:bg-gray-200">
              <i class="fas fa-expand-arrows-alt mr-1"></i>{{ allExpanded ? 'Свернуть' : 'Развернуть' }}
            </button>
          </div>
        </div>
        
        <!-- Статистика по типам файлов -->
        <div v-if="fileTreeStats" class="grid grid-cols-5 gap-2 mb-4">
          <div class="bg-orange-50 rounded-lg px-3 py-2 text-center">
            <div class="text-lg font-bold text-orange-700">{{ fileTreeStats.html }}</div>
            <div class="text-xs text-orange-600">HTML</div>
          </div>
          <div class="bg-blue-50 rounded-lg px-3 py-2 text-center">
            <div class="text-lg font-bold text-blue-700">{{ fileTreeStats.css }}</div>
            <div class="text-xs text-blue-600">CSS</div>
          </div>
          <div class="bg-yellow-50 rounded-lg px-3 py-2 text-center">
            <div class="text-lg font-bold text-yellow-700">{{ fileTreeStats.js }}</div>
            <div class="text-xs text-yellow-600">JS</div>
          </div>
          <div class="bg-green-50 rounded-lg px-3 py-2 text-center">
            <div class="text-lg font-bold text-green-700">{{ fileTreeStats.images }}</div>
            <div class="text-xs text-green-600">Картинки</div>
          </div>
          <div class="bg-gray-50 rounded-lg px-3 py-2 text-center">
            <div class="text-lg font-bold text-gray-700">{{ fileTreeStats.other }}</div>
            <div class="text-xs text-gray-600">Другое</div>
          </div>
        </div>
        
        <!-- Результаты проверки целостности -->
        <div v-if="integrityResult" class="mb-4">
          <div 
            class="rounded-lg border p-4"
            :class="integrityResult.is_complete ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-2">
                <i class="fas text-lg" :class="integrityResult.is_complete ? 'fa-check-circle text-green-600' : 'fa-exclamation-triangle text-red-600'"></i>
                <span class="font-bold" :class="integrityResult.is_complete ? 'text-green-800' : 'text-red-800'">
                  {{ integrityResult.is_complete ? 'Все ресурсы на месте' : `Пропущено ${integrityResult.total_missing} файлов` }}
                </span>
              </div>
              <div class="flex items-center space-x-2">
                <span class="text-xs text-gray-500">Проверено ссылок: {{ integrityResult.total_referenced }}</span>
                <button 
                  v-if="!integrityResult.is_complete"
                  @click="downloadAllMissing"
                  :disabled="downloadingMissing"
                  class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded text-white bg-orange-600 hover:bg-orange-700 disabled:opacity-50"
                >
                  <i class="fas mr-1" :class="downloadingMissing ? 'fa-spinner fa-spin' : 'fa-download'"></i>
                  Докачать все ({{ integrityResult.total_missing }})
                </button>
                <button @click="integrityResult = null" class="text-gray-400 hover:text-gray-600"><i class="fas fa-times"></i></button>
              </div>
            </div>
            
            <!-- Пропущенные по типам -->
            <div v-if="!integrityResult.is_complete" class="flex items-center space-x-4 mb-3 text-xs">
              <span v-if="integrityResult.missing_by_type.css > 0" class="text-blue-700 bg-blue-100 px-2 py-0.5 rounded">
                <i class="fas fa-file-code mr-1"></i>CSS: {{ integrityResult.missing_by_type.css }}
              </span>
              <span v-if="integrityResult.missing_by_type.js > 0" class="text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded">
                <i class="fas fa-file-code mr-1"></i>JS: {{ integrityResult.missing_by_type.js }}
              </span>
              <span v-if="integrityResult.missing_by_type.images > 0" class="text-green-700 bg-green-100 px-2 py-0.5 rounded">
                <i class="fas fa-file-image mr-1"></i>Картинки: {{ integrityResult.missing_by_type.images }}
              </span>
              <span v-if="integrityResult.missing_by_type.fonts > 0" class="text-purple-700 bg-purple-100 px-2 py-0.5 rounded">
                <i class="fas fa-font mr-1"></i>Шрифты: {{ integrityResult.missing_by_type.fonts }}
              </span>
              <span v-if="integrityResult.missing_by_type.other > 0" class="text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
                <i class="fas fa-file mr-1"></i>Другое: {{ integrityResult.missing_by_type.other }}
              </span>
            </div>
            
            <!-- Список пропущенных файлов -->
            <div v-if="integrityResult.missing && integrityResult.missing.length > 0" class="max-h-64 overflow-y-auto">
              <table class="w-full text-xs">
                <thead class="sticky top-0 bg-red-100">
                  <tr>
                    <th class="px-2 py-1 text-left font-semibold text-red-700">Пропущенный файл</th>
                    <th class="px-2 py-1 text-left font-semibold text-red-700">Где используется</th>
                    <th class="px-2 py-1 text-right font-semibold text-red-700">Ссылок</th>
                    <th class="px-2 py-1 text-right font-semibold text-red-700">Действие</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-red-100">
                  <tr v-for="item in integrityResult.missing" :key="item.path" class="hover:bg-red-100/50">
                    <td class="px-2 py-1 font-mono text-red-800 truncate max-w-xs" :title="item.path">{{ item.path }}</td>
                    <td class="px-2 py-1 text-gray-600 truncate max-w-xs" :title="item.referenced_by.join(', ')">{{ item.referenced_by[0] }}{{ item.referenced_by.length > 1 ? ` (+${item.referenced_by.length - 1})` : '' }}</td>
                    <td class="px-2 py-1 text-right text-gray-500">{{ item.ref_count }}</td>
                    <td class="px-2 py-1 text-right">
                      <button 
                        @click="downloadSingleMissing(item.path)"
                        class="text-orange-600 hover:text-orange-800"
                        title="Докачать этот файл"
                      >
                        <i class="fas fa-download"></i>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            
            <!-- Результат докачки -->
            <div v-if="downloadResult" class="mt-3 p-2 rounded border" :class="downloadResult.failed > 0 ? 'bg-yellow-50 border-yellow-200' : 'bg-green-50 border-green-200'">
              <div class="text-xs font-medium" :class="downloadResult.failed > 0 ? 'text-yellow-800' : 'text-green-800'">
                Докачано: {{ downloadResult.downloaded }} / {{ downloadResult.total }}
                <span v-if="downloadResult.failed > 0"> | Ошибок: {{ downloadResult.failed }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Дерево файлов -->
        <div v-if="fileTree && fileTree.children" class="border border-gray-200 rounded-lg overflow-hidden">
          <div class="divide-y divide-gray-100">
            <template v-for="node in fileTree.children" :key="node.path">
              <!-- Папка -->
              <div v-if="node.isDir">
                <div 
                  @click="toggleFolder(node.path)"
                  class="flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 cursor-pointer select-none transition-colors"
                  :style="{ paddingLeft: (node.depth * 16 + 12) + 'px' }"
                >
                  <div class="flex items-center space-x-2 min-w-0 flex-1">
                    <i class="fas text-xs transition-transform" :class="expandedFolders[node.path] ? 'fa-chevron-down text-gray-500' : 'fa-chevron-right text-gray-400'"></i>
                    <i class="fas fa-folder text-sm" :class="expandedFolders[node.path] ? 'fa-folder-open text-yellow-500' : 'fa-folder text-yellow-400'"></i>
                    <span class="text-sm font-semibold text-gray-700 truncate">{{ node.name }}</span>
                  </div>
                  <div class="flex items-center space-x-3 text-xs text-gray-500 flex-shrink-0 ml-2">
                    <select 
                      :value="folderTags[node.path] || ''"
                      @change="setFolderTag(node.path, $event.target.value)"
                      @click.stop
                      class="text-xs border rounded px-1 py-0.5 cursor-pointer w-20"
                      :class="getFolderTagInfo(folderTags[node.path]).color"
                    >
                      <option v-for="t in folderTagOptions" :key="t.id" :value="t.id">{{ t.label }}</option>
                    </select>
                    <span>{{ node.fileCount }} файлов</span>
                    <span class="font-mono">{{ node.sizeFormatted }}</span>
                    <span v-if="node.htmlCount > 0" class="text-orange-600">{{ node.htmlCount }} html</span>
                    <div class="flex items-center space-x-1" @click.stop>
                      <a :href="'/api/browse/' + folderName + '/' + node.path + '/'" target="_blank" class="text-blue-500 hover:text-blue-700" title="Открыть папку"><i class="fas fa-external-link-alt text-xs"></i></a>
                      <a v-if="node.name.includes('.')" :href="'https://' + node.name" target="_blank" class="text-green-500 hover:text-green-700" title="Оригинал онлайн"><i class="fas fa-globe text-xs"></i></a>
                      <button @click="checkFolderChanges(node)" class="text-purple-500 hover:text-purple-700" title="Проверить изменения"><i class="fas fa-search text-xs"></i></button>
                      <button @click="redownloadFolder(node)" class="text-orange-500 hover:text-orange-700" title="Перескачать папку"><i class="fas fa-sync-alt text-xs"></i></button>
                    </div>
                  </div>
                </div>
                
                <!-- Файлы внутри папки -->
                <template v-if="expandedFolders[node.path]">
                  <template v-for="child in node.children" :key="child.path">
                    <!-- Вложенная папка (рекурсия 1 уровень) -->
                    <div v-if="child.isDir">
                      <div 
                        @click="toggleFolder(child.path)"
                        class="flex items-center justify-between px-3 py-2 bg-gray-50/50 hover:bg-gray-100 cursor-pointer select-none transition-colors"
                        :style="{ paddingLeft: (child.depth * 16 + 12) + 'px' }"
                      >
                        <div class="flex items-center space-x-2 min-w-0 flex-1">
                          <i class="fas text-xs transition-transform" :class="expandedFolders[child.path] ? 'fa-chevron-down text-gray-500' : 'fa-chevron-right text-gray-400'"></i>
                          <i class="fas text-sm" :class="expandedFolders[child.path] ? 'fa-folder-open text-yellow-500' : 'fa-folder text-yellow-400'"></i>
                          <span class="text-sm font-medium text-gray-600 truncate">{{ child.name }}</span>
                        </div>
                        <div class="flex items-center space-x-3 text-xs text-gray-400 flex-shrink-0 ml-2">
                          <select 
                            :value="folderTags[child.path] || ''"
                            @change="setFolderTag(child.path, $event.target.value)"
                            @click.stop
                            class="text-xs border rounded px-1 py-0.5 cursor-pointer w-20"
                            :class="getFolderTagInfo(folderTags[child.path]).color"
                          >
                            <option v-for="t in folderTagOptions" :key="t.id" :value="t.id">{{ t.label }}</option>
                          </select>
                          <span>{{ child.fileCount }}</span>
                          <span class="font-mono">{{ child.sizeFormatted }}</span>
                          <div class="flex items-center space-x-1" @click.stop>
                            <a :href="'/api/browse/' + folderName + '/' + child.path + '/'" target="_blank" class="text-blue-500 hover:text-blue-700" title="Открыть папку"><i class="fas fa-external-link-alt text-xs"></i></a>
                            <button @click="checkFolderChanges(child)" class="text-purple-500 hover:text-purple-700" title="Проверить"><i class="fas fa-search text-xs"></i></button>
                            <button @click="redownloadFolder(child)" class="text-orange-500 hover:text-orange-700" title="Перескачать"><i class="fas fa-sync-alt text-xs"></i></button>
                          </div>
                        </div>
                      </div>
                      
                      <template v-if="expandedFolders[child.path]">
                        <div 
                          v-for="file in child.children" 
                          :key="file.path"
                          class="flex items-center justify-between px-3 py-1.5 hover:bg-blue-50 transition-colors"
                          :style="{ paddingLeft: (file.depth * 16 + 12) + 'px' }"
                        >
                          <div class="flex items-center space-x-2 min-w-0 flex-1">
                            <i class="fas text-xs" :class="fileIcon(file.type)"></i>
                            <span class="text-sm text-gray-800 truncate">{{ file.name }}</span>
                          </div>
                          <div class="flex items-center space-x-2 flex-shrink-0 ml-2">
                            <span class="text-xs text-gray-400 font-mono">{{ file.size }}</span>
                            <span class="text-xs text-gray-400">{{ file.date }}</span>
                            <div class="flex items-center space-x-1">
                              <a :href="'/api/browse/' + folderName + '/' + file.path" target="_blank" class="text-blue-500 hover:text-blue-700" title="Открыть"><i class="fas fa-eye text-xs"></i></a>
                              <a v-if="file.type === 'html'" :href="getOriginalUrl(file.path)" target="_blank" class="text-green-500 hover:text-green-700" title="Оригинал"><i class="fas fa-globe text-xs"></i></a>
                              <button v-if="file.type === 'html'" @click="checkPageChanges(file)" class="text-purple-500 hover:text-purple-700" title="Проверить"><i class="fas fa-search text-xs"></i></button>
                              <button v-if="file.type === 'html'" @click="redownloadPage(file)" class="text-orange-500 hover:text-orange-700" title="Перескачать"><i class="fas fa-sync-alt text-xs"></i></button>
                            </div>
                          </div>
                        </div>
                      </template>
                    </div>
                    
                    <!-- Файл -->
                    <div 
                      v-else
                      class="flex items-center justify-between px-3 py-1.5 hover:bg-blue-50 transition-colors"
                      :style="{ paddingLeft: (child.depth * 16 + 12) + 'px' }"
                    >
                      <div class="flex items-center space-x-2 min-w-0 flex-1">
                        <i class="fas text-xs" :class="fileIcon(child.type)"></i>
                        <span class="text-sm text-gray-800 truncate">{{ child.name }}</span>
                      </div>
                      <div class="flex items-center space-x-2 flex-shrink-0 ml-2">
                        <span class="text-xs text-gray-400 font-mono">{{ child.size }}</span>
                        <span class="text-xs text-gray-400">{{ child.date }}</span>
                        <div class="flex items-center space-x-1">
                          <a :href="'/api/browse/' + folderName + '/' + child.path" target="_blank" class="text-blue-500 hover:text-blue-700" title="Открыть"><i class="fas fa-eye text-xs"></i></a>
                          <a v-if="child.type === 'html'" :href="getOriginalUrl(child.path)" target="_blank" class="text-green-500 hover:text-green-700" title="Оригинал"><i class="fas fa-globe text-xs"></i></a>
                          <button v-if="child.type === 'html'" @click="checkPageChanges(child)" class="text-purple-500 hover:text-purple-700" title="Проверить"><i class="fas fa-search text-xs"></i></button>
                          <button v-if="child.type === 'html'" @click="redownloadPage(child)" class="text-orange-500 hover:text-orange-700" title="Перескачать"><i class="fas fa-sync-alt text-xs"></i></button>
                        </div>
                      </div>
                    </div>
                  </template>
                </template>
              </div>
              
              <!-- Файл в корне -->
              <div 
                v-else
                class="flex items-center justify-between px-3 py-1.5 hover:bg-blue-50 transition-colors"
                :style="{ paddingLeft: (node.depth * 16 + 12) + 'px' }"
              >
                <div class="flex items-center space-x-2 min-w-0 flex-1">
                  <i class="fas text-xs" :class="fileIcon(node.type)"></i>
                  <span class="text-sm text-gray-800 truncate">{{ node.name }}</span>
                </div>
                <div class="flex items-center space-x-2 flex-shrink-0 ml-2">
                  <span class="text-xs text-gray-400 font-mono">{{ node.size }}</span>
                  <span class="text-xs text-gray-400">{{ node.date }}</span>
                  <div class="flex items-center space-x-1">
                    <a :href="'/api/browse/' + folderName + '/' + node.path" target="_blank" class="text-blue-500 hover:text-blue-700" title="Открыть"><i class="fas fa-eye text-xs"></i></a>
                    <a v-if="node.type === 'html'" :href="getOriginalUrl(node.path)" target="_blank" class="text-green-500 hover:text-green-700" title="Оригинал"><i class="fas fa-globe text-xs"></i></a>
                    <button v-if="node.type === 'html'" @click="checkPageChanges(node)" class="text-purple-500 hover:text-purple-700" title="Проверить"><i class="fas fa-search text-xs"></i></button>
                    <button v-if="node.type === 'html'" @click="redownloadPage(node)" class="text-orange-500 hover:text-orange-700" title="Перескачать"><i class="fas fa-sync-alt text-xs"></i></button>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
        
        <div v-else-if="fileTreeLoading" class="bg-gray-50 rounded-lg p-6 text-center text-gray-500">
          <i class="fas fa-spinner fa-spin text-2xl mb-2"></i>
          <p>Загрузка дерева файлов...</p>
        </div>
        
        <div v-else class="bg-gray-50 rounded-lg p-6 text-center text-gray-500">
          <i class="fas fa-folder-open text-4xl mb-2"></i>
          <p>Нажмите "Обновить" для загрузки дерева файлов</p>
          <button @click="loadFileTree" class="btn btn-secondary mt-3">
            <i class="fas fa-sync-alt mr-2"></i>Загрузить дерево
          </button>
        </div>
      </div>
      
      <!-- ТАБ: Изменения -->
      <div v-show="activeTab === 'changes'" class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold text-gray-900 flex items-center">
            <i class="fas fa-exchange-alt mr-2 text-red-600"></i>
            Проверка изменений
          </h2>
          <div class="flex items-center space-x-2">
            <button 
              @click="checkAllChanges" 
              :disabled="changesLoading"
              class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
            >
              <i class="fas mr-1" :class="changesLoading ? 'fa-spinner fa-spin' : 'fa-search'"></i>
              {{ changesLoading ? 'Проверяю...' : 'Проверить все страницы' }}
            </button>
          </div>
        </div>
        
        <!-- Результаты проверки -->
        <div v-if="changesData">
          <!-- Сводка -->
          <div class="grid grid-cols-4 gap-3 mb-4">
            <div class="bg-gray-50 rounded-lg px-3 py-2 text-center">
              <div class="text-lg font-bold text-gray-700">{{ changesData.total }}</div>
              <div class="text-xs text-gray-500">Всего</div>
            </div>
            <div class="bg-red-50 rounded-lg px-3 py-2 text-center">
              <div class="text-lg font-bold text-red-700">{{ changesData.changed }}</div>
              <div class="text-xs text-red-600">Изменено</div>
            </div>
            <div class="bg-green-50 rounded-lg px-3 py-2 text-center">
              <div class="text-lg font-bold text-green-700">{{ changesData.unchanged }}</div>
              <div class="text-xs text-green-600">Актуально</div>
            </div>
            <div class="bg-yellow-50 rounded-lg px-3 py-2 text-center">
              <div class="text-lg font-bold text-yellow-700">{{ changesData.errors }}</div>
              <div class="text-xs text-yellow-600">Ошибок</div>
            </div>
          </div>
          
          <!-- Кнопка обновить все изменённые -->
          <div v-if="changesData.changed > 0" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between">
            <span class="text-sm text-red-800">
              <i class="fas fa-exclamation-triangle mr-2"></i>
              Обнаружено {{ changesData.changed }} изменённых страниц
            </span>
            <button 
              @click="updateAllChanged"
              :disabled="updatingPages"
              class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded text-white bg-orange-600 hover:bg-orange-700 disabled:opacity-50"
            >
              <i class="fas mr-1" :class="updatingPages ? 'fa-spinner fa-spin' : 'fa-download'"></i>
              Обновить все ({{ changesData.changed }})
            </button>
          </div>
          
          <!-- Фильтр -->
          <div class="flex items-center space-x-2 mb-3">
            <button 
              @click="changesFilter = 'all'"
              class="px-2 py-1 text-xs rounded"
              :class="changesFilter === 'all' ? 'bg-gray-700 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            >Все</button>
            <button 
              @click="changesFilter = 'changed'"
              class="px-2 py-1 text-xs rounded"
              :class="changesFilter === 'changed' ? 'bg-red-600 text-white' : 'bg-red-50 text-red-600 hover:bg-red-100'"
            >Изменённые</button>
            <button 
              @click="changesFilter = 'unchanged'"
              class="px-2 py-1 text-xs rounded"
              :class="changesFilter === 'unchanged' ? 'bg-green-600 text-white' : 'bg-green-50 text-green-600 hover:bg-green-100'"
            >Актуальные</button>
            <button 
              @click="changesFilter = 'error'"
              class="px-2 py-1 text-xs rounded"
              :class="changesFilter === 'error' ? 'bg-yellow-600 text-white' : 'bg-yellow-50 text-yellow-600 hover:bg-yellow-100'"
            >Ошибки</button>
          </div>
          
          <!-- Таблица страниц -->
          <div class="border border-gray-200 rounded-lg overflow-hidden">
            <table class="w-full text-sm">
              <thead class="bg-gray-50 border-b">
                <tr>
                  <th class="px-3 py-2 text-left font-semibold text-gray-600">Страница</th>
                  <th class="px-3 py-2 text-left font-semibold text-gray-600">Статус</th>
                  <th class="px-3 py-2 text-left font-semibold text-gray-600">Размер</th>
                  <th class="px-3 py-2 text-left font-semibold text-gray-600">Изменения</th>
                  <th class="px-3 py-2 text-right font-semibold text-gray-600">Действия</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr 
                  v-for="page in filteredChangesPages" 
                  :key="page.page"
                  class="hover:bg-gray-50"
                  :class="page.has_changes ? 'bg-red-50/30' : ''"
                >
                  <td class="px-3 py-2">
                    <div class="font-mono text-xs text-gray-800 truncate max-w-xs" :title="page.page">{{ page.page }}</div>
                  </td>
                  <td class="px-3 py-2">
                    <span v-if="page.status === 'changed'" class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      <i class="fas fa-exclamation-circle mr-1"></i>Изменено
                    </span>
                    <span v-else-if="page.status === 'unchanged'" class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <i class="fas fa-check-circle mr-1"></i>Актуально
                    </span>
                    <span v-else class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      <i class="fas fa-times-circle mr-1"></i>Ошибка
                    </span>
                  </td>
                  <td class="px-3 py-2 text-xs text-gray-500">
                    <span>{{ page.local_size }}</span>
                    <span v-if="page.online_size && page.size_diff !== 0" class="ml-1" :class="page.size_diff > 0 ? 'text-green-600' : 'text-red-600'">
                      ({{ page.size_diff > 0 ? '+' : '' }}{{ page.size_diff }} B)
                    </span>
                  </td>
                  <td class="px-3 py-2 text-xs">
                    <div v-if="page.has_changes">
                      <div v-if="page.title_changed" class="text-red-600">
                        <i class="fas fa-heading mr-1"></i>Title: "{{ page.local_title }}" -> "{{ page.online_title }}"
                      </div>
                      <div v-if="page.online_elements && page.local_elements" class="text-gray-500">
                        Элементов: {{ page.local_elements }} -> {{ page.online_elements }}
                      </div>
                    </div>
                    <span v-else-if="page.error" class="text-yellow-600">{{ page.error }}</span>
                    <span v-else class="text-gray-400">-</span>
                  </td>
                  <td class="px-3 py-2 text-right">
                    <div class="flex items-center justify-end space-x-1">
                      <a :href="page.online_url" target="_blank" class="text-green-500 hover:text-green-700" title="Онлайн версия">
                        <i class="fas fa-globe text-xs"></i>
                      </a>
                      <a :href="'/api/browse/' + folderName + '/' + page.page" target="_blank" class="text-blue-500 hover:text-blue-700" title="Локальная версия">
                        <i class="fas fa-eye text-xs"></i>
                      </a>
                      <button 
                        v-if="page.has_changes"
                        @click="updateSinglePage(page)"
                        class="text-orange-500 hover:text-orange-700"
                        title="Обновить страницу"
                      >
                        <i class="fas fa-download text-xs"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          
          <div class="mt-2 text-xs text-gray-400 text-right">
            Проверено: {{ changesData.checked_at }}
          </div>
        </div>
        
        <!-- Пустое состояние -->
        <div v-else class="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
          <i class="fas fa-search text-4xl mb-3"></i>
          <p>Нажмите "Проверить все страницы" для сравнения с онлайн версией</p>
        </div>
      </div>
      
      <!-- ТАБ: Информация -->
      <div v-show="activeTab === 'info'" class="card">
        <h2 class="text-lg font-bold text-gray-900 flex items-center mb-4">
          <i class="fas fa-info-circle mr-2 text-purple-600"></i>
          Подробная информация
        </h2>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-3">
            <h3 class="text-sm font-semibold text-gray-700 border-b pb-1">Основное</h3>
            <div class="text-sm space-y-2">
              <div class="flex justify-between">
                <span class="text-gray-500">Домен:</span>
                <span class="text-gray-900 font-medium">{{ siteData.domain }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Папка:</span>
                <span class="text-gray-900 font-mono text-xs">{{ siteData.folder_name }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Движок:</span>
                <span class="text-gray-900">{{ siteData.engine || 'wget2' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Дата скачивания:</span>
                <span class="text-gray-900">{{ siteData.date }}</span>
              </div>
              <div v-if="siteData.url" class="flex justify-between">
                <span class="text-gray-500">URL:</span>
                <a :href="siteData.url" target="_blank" class="text-blue-600 hover:underline text-xs truncate max-w-[200px]">{{ siteData.url }}</a>
              </div>
            </div>
          </div>
          
          <div class="space-y-3">
            <h3 class="text-sm font-semibold text-gray-700 border-b pb-1">Статистика</h3>
            <div class="text-sm space-y-2">
              <div class="flex justify-between">
                <span class="text-gray-500">Всего файлов:</span>
                <span class="text-gray-900 font-bold">{{ siteData.files || 0 }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Размер:</span>
                <span class="text-gray-900 font-bold">{{ siteData.size || '0 B' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Поддоменов:</span>
                <span class="text-gray-900 font-bold">{{ subdomains.length }}</span>
              </div>
              <div v-if="fileTreeStats" class="flex justify-between">
                <span class="text-gray-500">HTML страниц:</span>
                <span class="text-gray-900 font-bold">{{ fileTreeStats.html }}</span>
              </div>
              <div v-if="fileTreeStats" class="flex justify-between">
                <span class="text-gray-500">CSS файлов:</span>
                <span class="text-gray-900">{{ fileTreeStats.css }}</span>
              </div>
              <div v-if="fileTreeStats" class="flex justify-between">
                <span class="text-gray-500">JS файлов:</span>
                <span class="text-gray-900">{{ fileTreeStats.js }}</span>
              </div>
              <div v-if="fileTreeStats" class="flex justify-between">
                <span class="text-gray-500">Картинок:</span>
                <span class="text-gray-900">{{ fileTreeStats.images }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <div v-if="siteData.path" class="mt-4 pt-3 border-t">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">Путь на диске</h3>
          <div class="bg-gray-50 rounded px-3 py-2 font-mono text-xs text-gray-700 break-all">{{ siteData.path }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLandingsStore } from '../stores/landings'

const route = useRoute()
const router = useRouter()
const landingsStore = useLandingsStore()

const loading = ref(true)
const error = ref(null)
const siteData = ref({})
const sortBy = ref('tag')
const filterTag = ref('')
const onlyRelevant = ref(false)
const activeTab = ref('subdomains')
const fileTreeData = ref(null)
const fileTreeLoading = ref(false)
const expandedFolders = ref({})
const allExpanded = ref(false)
const integrityResult = ref(null)
const integrityLoading = ref(false)
const downloadingMissing = ref(false)
const downloadResult = ref(null)
const folderTags = ref({})
const changesData = ref(null)
const changesLoading = ref(false)
const changesFilter = ref('all')
const updatingPages = ref(false)
const thumbnailUrl = ref(null)
const thumbnailError = ref(false)
const generatingThumb = ref(false)
const activeJob = ref(null)

const folderTagOptions = [
  { id: '', label: '--', color: 'text-gray-400', bg: '' },
  { id: 'important', label: 'Важно', color: 'text-red-600', bg: 'bg-red-50', icon: 'fa-star' },
  { id: 'content', label: 'Контент', color: 'text-green-600', bg: 'bg-green-50', icon: 'fa-file-alt' },
  { id: 'assets', label: 'Ресурсы', color: 'text-blue-600', bg: 'bg-blue-50', icon: 'fa-images' },
  { id: 'ignore', label: 'Игнор', color: 'text-gray-400', bg: 'bg-gray-100', icon: 'fa-ban' }
]

const availableTags = [
  { id: 'landing', label: 'Лендинг', icon: 'fas fa-star', priority: 1, activeClass: 'bg-blue-600 text-white', inactiveClass: 'bg-blue-50 text-blue-700 hover:bg-blue-100', selectClass: 'text-blue-700 border-blue-300' },
  { id: 'content', label: 'Контент', icon: 'fas fa-file-alt', priority: 2, activeClass: 'bg-green-600 text-white', inactiveClass: 'bg-green-50 text-green-700 hover:bg-green-100', selectClass: 'text-green-700 border-green-300' },
  { id: 'api', label: 'API', icon: 'fas fa-plug', priority: 3, activeClass: 'bg-purple-600 text-white', inactiveClass: 'bg-purple-50 text-purple-700 hover:bg-purple-100', selectClass: 'text-purple-700 border-purple-300' },
  { id: 'cdn', label: 'CDN', icon: 'fas fa-cloud', priority: 4, activeClass: 'bg-yellow-500 text-white', inactiveClass: 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100', selectClass: 'text-yellow-700 border-yellow-300' },
  { id: 'tracker', label: 'Трекер', icon: 'fas fa-chart-bar', priority: 5, activeClass: 'bg-red-600 text-white', inactiveClass: 'bg-red-50 text-red-700 hover:bg-red-100', selectClass: 'text-red-700 border-red-300' },
  { id: 'ads', label: 'Реклама', icon: 'fas fa-ad', priority: 6, activeClass: 'bg-orange-500 text-white', inactiveClass: 'bg-orange-50 text-orange-700 hover:bg-orange-100', selectClass: 'text-orange-700 border-orange-300' },
  { id: 'junk', label: 'Мусор', icon: 'fas fa-trash', priority: 7, activeClass: 'bg-gray-600 text-white', inactiveClass: 'bg-gray-100 text-gray-700 hover:bg-gray-200', selectClass: 'text-gray-500 border-gray-300' }
]

const folderName = computed(() => route.params.folder)

const previewUrl = computed(() => {
  if (!folderName.value) return null
  return `/api/browse/${folderName.value}/index.html`
})

const subdomains = computed(() => {
  if (siteData.value.subdomains && Array.isArray(siteData.value.subdomains)) {
    return siteData.value.subdomains.map(sub => {
      if (typeof sub === 'object' && sub.name) {
        const config = sub.config || {}
        return {
          name: sub.name,
          files: sub.files || 0,
          size: sub.size || '0 B',
          size_bytes: sub.size_bytes || 0,
          date: sub.date || '',
          pages: sub.pages || [],
          config_key: sub.config_key || '',
          config: config,
          tag: config.tag || '',
          excluded: config.excluded === true,
          hasIndex: (sub.pages || []).some(p => p.name === 'index.html')
        }
      }
      return { name: sub, files: 0, size: '0 B', size_bytes: 0, date: '', pages: [], config_key: '', config: {}, tag: '', excluded: false, hasIndex: false }
    })
  }
  return []
})

const excludedCount = computed(() => {
  return subdomains.value.filter(s => s.excluded).length
})

const tagCounts = computed(() => {
  const counts = {}
  for (const sub of subdomains.value) {
    if (sub.tag) {
      counts[sub.tag] = (counts[sub.tag] || 0) + 1
    }
  }
  return counts
})

function getTagInfo(tagId) {
  const tag = availableTags.find(t => t.id === tagId)
  return tag || { selectClass: '', priority: 99 }
}

const filteredSubdomains = computed(() => {
  let list = subdomains.value
  
  // Filtr "Tolko svoi + CDN"
  if (onlyRelevant.value) {
    // Izvlekaem kornevoj domen iz folder_name ili domain
    const baseDomain = siteData.value.domain || folderName.value || ''
    // Poluchaem kornevoj domen (poslednie 2 chasti, naprimer eagles.com)
    const parts = baseDomain.split('.')
    const rootDomain = parts.length >= 2 ? parts.slice(-2).join('.') : baseDomain
    
    list = list.filter(s => {
      const name = s.name.toLowerCase()
      // 1. Poddomen tekuschego sajta (soderzhit rootDomain)
      if (name.includes(rootDomain.toLowerCase())) return true
      // 2. CDN po tegu
      if (s.tag === 'cdn') return true
      // 3. CDN po imeni (cdn, static, assets, cloudfront, cloudflare, fastly, akamai)
      if (name.includes('cdn') || name.includes('static') || name.includes('assets') ||
          name.includes('cloudfront') || name.includes('cloudflare') || 
          name.includes('fastly') || name.includes('akamai') ||
          name.includes('jsdelivr') || name.includes('unpkg')) return true
      return false
    })
  }
  
  if (filterTag.value) {
    list = list.filter(s => s.tag === filterTag.value)
  }
  
  const tagPriority = (t) => {
    const found = availableTags.find(at => at.id === t)
    return found ? found.priority : 50
  }
  
  list = [...list].sort((a, b) => {
    if (sortBy.value === 'tag') {
      const pa = tagPriority(a.tag)
      const pb = tagPriority(b.tag)
      if (pa !== pb) return pa - pb
      return a.name.localeCompare(b.name)
    }
    if (sortBy.value === 'files') return b.files - a.files
    if (sortBy.value === 'size') return (b.size_bytes || b.files) - (a.size_bytes || a.files)
    return a.name.localeCompare(b.name)
  })
  
  return list
})

const pages = computed(() => {
  if (siteData.value.pages && siteData.value.pages.length > 0) {
    return siteData.value.pages.map(page => ({
      name: page.name || page.path.split('/').pop(),
      path: page.path,
      folder: page.subdomain || page.path.split('/').slice(0, -1).join('/') || '/',
      size: page.size || '',
      size_bytes: page.size_bytes || 0,
      date: page.date || '',
      url: `/api/browse/${folderName.value}/${page.path}`,
      originalUrl: siteData.value.domain
        ? `https://${siteData.value.domain}/${page.path}`
        : (siteData.value.original_url ? siteData.value.original_url.replace(/\/$/, '') + '/' + page.path : '')
    }))
  }
  return []
})

const groupedPages = computed(() => {
  const groups = {}
  for (const page of pages.value) {
    const key = page.folder || '/'
    if (!groups[key]) {
      groups[key] = { folder: key, pages: [] }
    }
    groups[key].pages.push(page)
  }
  // Сортировка: корень первым, потом по имени папки
  const sorted = Object.values(groups).sort((a, b) => {
    if (a.folder === '/') return -1
    if (b.folder === '/') return 1
    return a.folder.localeCompare(b.folder)
  })
  return sorted
})

const fileTreeStats = computed(() => {
  if (!fileTreeData.value) return null
  return fileTreeData.value.stats
})

function formatSizeLocal(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const fileTree = computed(() => {
  if (!fileTreeData.value || !fileTreeData.value.files) return null
  
  // Build tree from flat file list
  const root = { name: '/', path: '', isDir: true, depth: 0, children: [], size_bytes: 0, fileCount: 0, htmlCount: 0 }
  
  for (const file of fileTreeData.value.files) {
    const parts = file.path.split('/')
    let current = root
    
    // Create/traverse directories
    for (let i = 0; i < parts.length - 1; i++) {
      const dirName = parts[i]
      const dirPath = parts.slice(0, i + 1).join('/')
      let dirNode = current.children.find(c => c.isDir && c.name === dirName)
      
      if (!dirNode) {
        dirNode = { name: dirName, path: dirPath, isDir: true, depth: i + 1, children: [], size_bytes: 0, fileCount: 0, htmlCount: 0 }
        current.children.push(dirNode)
      }
      
      dirNode.size_bytes += file.size_bytes
      dirNode.fileCount += 1
      if (file.type === 'html') dirNode.htmlCount += 1
      
      current = dirNode
    }
    
    // Add file node
    current.children.push({
      name: file.name,
      path: file.path,
      isDir: false,
      depth: parts.length,
      size: file.size,
      size_bytes: file.size_bytes,
      date: file.date,
      type: file.type,
      ext: file.ext
    })
    
    root.size_bytes += file.size_bytes
    root.fileCount += 1
    if (file.type === 'html') root.htmlCount += 1
  }
  
  // Format sizes for directories
  function formatDirSizes(node) {
    if (node.isDir) {
      node.sizeFormatted = formatSizeLocal(node.size_bytes)
      // Sort: dirs first, then files; alphabetical within each group
      node.children.sort((a, b) => {
        if (a.isDir && !b.isDir) return -1
        if (!a.isDir && b.isDir) return 1
        return a.name.localeCompare(b.name)
      })
      node.children.forEach(formatDirSizes)
    }
  }
  formatDirSizes(root)
  
  return root
})

function fileIcon(type) {
  switch (type) {
    case 'html': return 'fa-file-code text-orange-500'
    case 'css': return 'fa-file-code text-blue-500'
    case 'js': return 'fa-file-code text-yellow-600'
    case 'image': return 'fa-file-image text-green-500'
    default: return 'fa-file text-gray-400'
  }
}

function toggleFolder(path) {
  expandedFolders.value = { ...expandedFolders.value, [path]: !expandedFolders.value[path] }
}

function toggleAllFolders() {
  if (allExpanded.value) {
    expandedFolders.value = {}
    allExpanded.value = false
  } else {
    // Expand all directories
    const expanded = {}
    function collectDirs(node) {
      if (node.isDir && node.children) {
        expanded[node.path] = true
        node.children.forEach(collectDirs)
      }
    }
    if (fileTree.value) {
      fileTree.value.children.forEach(collectDirs)
    }
    expandedFolders.value = expanded
    allExpanded.value = true
  }
}

async function loadFileTree() {
  fileTreeLoading.value = true
  try {
    const response = await fetch(`/api/file-tree/${folderName.value}`)
    const data = await response.json()
    fileTreeData.value = data
    // Auto-expand first level
    if (data.files) {
      const firstLevel = {}
      for (const f of data.files) {
        const firstDir = f.path.split('/')[0]
        if (f.path.includes('/')) {
          firstLevel[firstDir] = true
        }
      }
      expandedFolders.value = firstLevel
    }
  } catch (err) {
    console.error('Ошибка загрузки дерева файлов:', err)
  } finally {
    fileTreeLoading.value = false
  }
}

function getOriginalUrl(filePath) {
  // Check if path starts with a subdomain-like folder
  const parts = filePath.split('/')
  if (parts.length > 1 && parts[0].includes('.')) {
    return `https://${parts[0]}/${parts.slice(1).join('/')}`
  }
  if (siteData.value.domain) {
    return `https://${siteData.value.domain}/${filePath}`
  }
  if (siteData.value.job && siteData.value.job.url) {
    return siteData.value.job.url.replace(/\/$/, '') + '/' + filePath
  }
  // Fallback: folder_name is domain
  return `https://${folderName.value}/${filePath}`
}

async function redownloadPage(file) {
  const originalUrl = getOriginalUrl(file.path)
  if (!originalUrl) {
    alert('Не удалось определить URL оригинала.')
    return
  }
  if (!confirm(`Перескачать "${file.name}"?\n\nURL: ${originalUrl}`)) return
  
  try {
    const response = await fetch('/api/landings/redownload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: originalUrl,
        folder_name: folderName.value,
        config_key: ''
      })
    })
    const data = await response.json()
    if (data.id) {
      alert(`Перескачивание запущено!\nJob ID: ${data.id}`)
    } else {
      alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'))
    }
  } catch (err) {
    alert('Ошибка: ' + err.message)
  }
}

const filteredChangesPages = computed(() => {
  if (!changesData.value || !changesData.value.pages) return []
  if (changesFilter.value === 'all') return changesData.value.pages
  return changesData.value.pages.filter(p => p.status === changesFilter.value)
})

async function checkAllChanges() {
  changesLoading.value = true
  changesData.value = null
  try {
    const response = await fetch(`/api/check-all-changes/${folderName.value}?max=100`)
    const data = await response.json()
    changesData.value = data
  } catch (err) {
    alert('Ошибка проверки: ' + err.message)
  } finally {
    changesLoading.value = false
  }
}

async function updateAllChanged() {
  if (!changesData.value) return
  const changedPages = changesData.value.pages.filter(p => p.has_changes)
  if (changedPages.length === 0) return
  
  if (!confirm(`Обновить ${changedPages.length} изменённых страниц?`)) return
  
  updatingPages.value = true
  const paths = changedPages.map(p => p.page)
  
  try {
    const response = await fetch(`/api/download-missing/${folderName.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    })
    const data = await response.json()
    alert(`Обновлено: ${data.downloaded} / ${data.total}\n${data.failed > 0 ? 'Ошибок: ' + data.failed : ''}`)
    // Refresh changes
    await checkAllChanges()
  } catch (err) {
    alert('Ошибка: ' + err.message)
  } finally {
    updatingPages.value = false
  }
}

async function updateSinglePage(page) {
  try {
    const response = await fetch(`/api/download-missing/${folderName.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: [page.page] })
    })
    const data = await response.json()
    if (data.downloaded > 0) {
      // Update status in local data
      page.status = 'unchanged'
      page.has_changes = false
      changesData.value.changed--
      changesData.value.unchanged++
    } else {
      alert('Не удалось обновить: ' + (data.errors?.[0] || 'Неизвестная ошибка'))
    }
  } catch (err) {
    alert('Ошибка: ' + err.message)
  }
}

async function generateThumbnail() {
  generatingThumb.value = true
  try {
    const response = await fetch(`/api/screenshot/${folderName.value}`, { method: 'POST' })
    const data = await response.json()
    if (data.path) {
      thumbnailUrl.value = `/api/thumbnail/${folderName.value}?t=${Date.now()}`
      thumbnailError.value = false
    } else {
      alert('Не удалось создать скриншот: ' + (data.error || 'Неизвестная ошибка'))
    }
  } catch (err) {
    alert('Ошибка: ' + err.message)
  } finally {
    generatingThumb.value = false
  }
}

async function redownloadSite() {
  if (!confirm('Перекачать весь сайт? Это удалит текущую версию и скачает заново.')) return
  
  try {
    const response = await fetch(`/api/downloads/${folderName.value}/restart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        engine: siteData.value.engine || 'smart'
      })
    })
    const data = await response.json()
    if (data.id) {
      activeJob.value = { id: data.id, progress: 0 }
      pollJobProgress(data.id)
      alert('Перекачивание запущено!')
    } else {
      alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'))
    }
  } catch (err) {
    alert('Ошибка: ' + err.message)
  }
}

let pollInterval = null

function pollJobProgress(jobId) {
  if (pollInterval) clearInterval(pollInterval)
  
  pollInterval = setInterval(async () => {
    try {
      const response = await fetch(`/api/status/${jobId}`)
      const data = await response.json()
      
      activeJob.value = {
        id: jobId,
        progress: data.progress || 0,
        files: data.files_downloaded || 0,
        size: data.total_size || '0 B',
        lastLog: data.output_lines?.slice(-1)[0] || 'Скачивание...'
      }
      
      if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
        clearInterval(pollInterval)
        pollInterval = null
        activeJob.value = null
        loadSiteData()
      }
    } catch (err) {
      clearInterval(pollInterval)
      pollInterval = null
      activeJob.value = null
    }
  }, 1500)
}

async function stopRedownload() {
  if (!activeJob.value?.id) return
  if (!confirm('Остановить перекачивание?')) return
  
  try {
    await fetch(`/api/stop/${activeJob.value.id}`, { method: 'POST' })
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
    activeJob.value = null
  } catch (err) {
    alert('Ошибка: ' + err.message)
  }
}

function loadThumbnail() {
  // Check if thumbnail exists
  thumbnailUrl.value = `/api/thumbnail/${folderName.value}`
}

function goToSubdomainFiles(subdomain) {
  // Switch to files tab and expand the subdomain folder
  activeTab.value = 'files'
  // Expand the subdomain folder in the tree
  expandedFolders.value[subdomain.name] = true
  allExpanded.value = false
}

function setFolderTag(folderPath, tagId) {
  folderTags.value[folderPath] = tagId
  // Save to localStorage
  const key = `folderTags_${folderName.value}`
  localStorage.setItem(key, JSON.stringify(folderTags.value))
}

function loadFolderTags() {
  const key = `folderTags_${folderName.value}`
  const saved = localStorage.getItem(key)
  if (saved) {
    try {
      folderTags.value = JSON.parse(saved)
    } catch (e) {
      folderTags.value = {}
    }
  }
}

function getFolderTagInfo(tagId) {
  return folderTagOptions.find(t => t.id === tagId) || folderTagOptions[0]
}

async function checkFolderChanges(folderNode) {
  // Check changes for all HTML files in this folder
  const htmlFiles = []
  function collectHtml(node) {
    if (node.isDir && node.children) {
      node.children.forEach(collectHtml)
    } else if (node.type === 'html') {
      htmlFiles.push(node)
    }
  }
  collectHtml(folderNode)
  
  if (htmlFiles.length === 0) {
    alert(`Папка "${folderNode.name}" не содержит HTML файлов для проверки.`)
    return
  }
  
  alert(`Проверяю ${htmlFiles.length} HTML файлов в "${folderNode.name}"...`)
  
  let changed = 0
  let errors = 0
  let upToDate = 0
  
  for (const file of htmlFiles) {
    try {
      const response = await fetch(`/api/check-changes/${folderName.value}?page=${encodeURIComponent(file.path)}`)
      const result = await response.json()
      if (result.error) errors++
      else if (result.has_changes) changed++
      else upToDate++
    } catch (err) {
      errors++
    }
  }
  
  alert(`Проверка "${folderNode.name}":\n\nВсего HTML: ${htmlFiles.length}\nИзменено: ${changed}\nАктуально: ${upToDate}\nОшибок: ${errors}`)
}

async function redownloadFolder(folderNode) {
  // Collect all HTML files in folder to redownload
  const htmlFiles = []
  function collectHtml(node) {
    if (node.isDir && node.children) {
      node.children.forEach(collectHtml)
    } else if (node.type === 'html') {
      htmlFiles.push(node)
    }
  }
  collectHtml(folderNode)
  
  if (htmlFiles.length === 0) {
    alert(`Папка "${folderNode.name}" не содержит HTML файлов.`)
    return
  }
  
  if (!confirm(`Перескачать ${htmlFiles.length} HTML файлов из "${folderNode.name}"?`)) return
  
  const paths = htmlFiles.map(f => f.path)
  try {
    const response = await fetch(`/api/download-missing/${folderName.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    })
    const data = await response.json()
    alert(`Перескачано: ${data.downloaded} / ${data.total}\n${data.failed > 0 ? 'Ошибок: ' + data.failed : ''}`)
    if (data.downloaded > 0) loadFileTree()
  } catch (err) {
    alert('Ошибка: ' + err.message)
  }
}

async function checkIntegrity() {
  integrityLoading.value = true
  integrityResult.value = null
  downloadResult.value = null
  try {
    const response = await fetch(`/api/check-integrity/${folderName.value}`)
    const data = await response.json()
    integrityResult.value = data
  } catch (err) {
    alert('Ошибка проверки целостности: ' + err.message)
  } finally {
    integrityLoading.value = false
  }
}

async function downloadAllMissing() {
  if (!integrityResult.value || !integrityResult.value.missing) return
  const paths = integrityResult.value.missing.map(m => m.path)
  if (!confirm(`Докачать ${paths.length} файлов?`)) return
  
  downloadingMissing.value = true
  downloadResult.value = null
  try {
    const response = await fetch(`/api/download-missing/${folderName.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    })
    const data = await response.json()
    downloadResult.value = data
    // Refresh integrity check and file tree
    if (data.downloaded > 0) {
      loadFileTree()
    }
  } catch (err) {
    alert('Ошибка докачки: ' + err.message)
  } finally {
    downloadingMissing.value = false
  }
}

async function downloadSingleMissing(path) {
  try {
    const response = await fetch(`/api/download-missing/${folderName.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: [path] })
    })
    const data = await response.json()
    if (data.downloaded > 0) {
      alert(`Скачан: ${path}`)
      // Remove from missing list
      if (integrityResult.value && integrityResult.value.missing) {
        integrityResult.value.missing = integrityResult.value.missing.filter(m => m.path !== path)
        integrityResult.value.total_missing = integrityResult.value.missing.length
        integrityResult.value.is_complete = integrityResult.value.missing.length === 0
      }
    } else {
      alert(`Не удалось скачать: ${path}\n${data.results?.[0]?.error || ''}`)
    }
  } catch (err) {
    alert('Ошибка: ' + err.message)
  }
}

const lastCheck = ref(null)

const changesStatus = computed(() => {
  if (!lastCheck.value) {
    return {
      icon: 'fas fa-question-circle',
      text: 'Не проверялось',
      textClass: 'text-gray-600',
      bgClass: 'bg-gray-50'
    }
  }
  
  if (lastCheck.value.has_changes) {
    return {
      icon: 'fas fa-exclamation-triangle',
      text: 'Обнаружены изменения!',
      textClass: 'text-red-600',
      bgClass: 'bg-red-50'
    }
  }
  
  return {
    icon: 'fas fa-check-circle',
    text: 'Актуальная версия',
    textClass: 'text-green-600',
    bgClass: 'bg-green-50'
  }
})

const statusBadgeClass = computed(() => {
  if (siteData.value.is_active) return 'bg-blue-100 text-blue-800'
  if (siteData.value.job?.status === 'completed') return 'bg-green-100 text-green-800'
  if (siteData.value.job?.status === 'failed') return 'bg-red-100 text-red-800'
  return 'bg-gray-100 text-gray-800'
})

const statusIcon = computed(() => {
  if (siteData.value.is_active) return 'fas fa-spinner fa-spin'
  if (siteData.value.job?.status === 'completed') return 'fas fa-check'
  if (siteData.value.job?.status === 'failed') return 'fas fa-times'
  return 'fas fa-check-circle'
})

const statusText = computed(() => {
  if (siteData.value.is_active) return 'Скачивается'
  if (siteData.value.job?.status === 'completed') return 'Завершено'
  if (siteData.value.job?.status === 'failed') return 'Ошибка'
  return 'Скачано'
})

async function loadSiteData() {
  loading.value = true
  error.value = null
  
  try {
    await landingsStore.loadLandings()
    
    // Найти сайт в списке лендингов
    for (const domain of landingsStore.landings) {
      const folder = domain.folders.find(f => f.folder_name === folderName.value)
      if (folder) {
        siteData.value = folder
        loading.value = false
        return
      }
    }
    
    error.value = 'Сайт не найден'
  } catch (e) {
    error.value = 'Ошибка загрузки данных: ' + e.message
  } finally {
    loading.value = false
  }
}

async function openInBrowser() {
  try {
    const response = await fetch(`/api/find-index/${folderName.value}`)
    const data = await response.json()
    
    if (data.index_path) {
      window.open(`/api/browse/${folderName.value}/${data.index_path}`, '_blank')
    } else {
      alert('Не найден index.html файл')
    }
  } catch (err) {
    alert('Ошибка открытия сайта: ' + err.message)
  }
}

function openFolder() {
  fetch(`/api/open-folder?path=${encodeURIComponent(siteData.value.path)}`)
    .catch(err => console.error('Ошибка открытия папки:', err))
}

function openSubdomain(subdomain) {
  const indexPage = subdomain.pages.find(p => p.name === 'index.html')
  if (indexPage) {
    window.open(`/api/browse/${folderName.value}/${indexPage.path}`, '_blank')
  }
}

function openSubdomainFolder(subdomain) {
  const subPath = siteData.value.path + '/' + subdomain.name
  fetch(`/api/open-folder?path=${encodeURIComponent(subPath)}`)
    .catch(err => console.error('Ошибка открытия папки поддомена:', err))
}

async function downloadSubdomain(subdomain) {
  const url = `https://${subdomain.name}`
  try {
    const response = await fetch('/api/landings/redownload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        folder_name: folderName.value,
        config_key: subdomain.config_key
      })
    })
    const data = await response.json()
    if (data.id) {
      alert(`Скачивание запущено!\nJob ID: ${data.id}\nURL: ${url}`)
    } else {
      alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'))
    }
  } catch (err) {
    alert('Ошибка запуска скачивания: ' + err.message)
  }
}

async function redownloadSubdomain(subdomain) {
  if (!confirm(`Перескачать поддомен "${subdomain.name}"?\n\nЭто обновит все файлы.`)) return
  
  const url = `https://${subdomain.name}`
  try {
    const response = await fetch('/api/landings/redownload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        folder_name: folderName.value,
        config_key: subdomain.config_key
      })
    })
    const data = await response.json()
    if (data.id) {
      alert(`Перескачивание запущено!\nJob ID: ${data.id}\nURL: ${url}`)
    } else {
      alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'))
    }
  } catch (err) {
    alert('Ошибка запуска перескачивания: ' + err.message)
  }
}

async function checkPageChanges(page) {
  const origUrl = page.originalUrl || getOriginalUrl(page.path)
  if (!origUrl) {
    alert('Не удалось определить URL оригинала для этой страницы.')
    return
  }
  
  try {
    const response = await fetch(`/api/check-changes/${folderName.value}?page=${encodeURIComponent(page.path)}`)
    const result = await response.json()
    
    let message = `Проверка: ${page.name}\n`
    message += `Путь: ${page.path}\n\n`
    
    if (result.error) {
      message += `Ошибка: ${result.error}`
    } else if (result.has_changes) {
      message += 'ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ!\n\n'
      if (result.title_changed) {
        message += `Заголовок:\n  Локально: "${result.local_title}"\n  Онлайн: "${result.online_title}"\n\n`
      }
      if (result.size_changed) {
        message += `Размер:\n  Локально: ${result.local_size}\n  Онлайн: ${result.online_size}\n\n`
      }
      if (result.local_hash && result.online_hash) {
        message += `MD5:\n  Локально: ${result.local_hash.substring(0, 8)}...\n  Онлайн: ${result.online_hash.substring(0, 8)}...\n\n`
      }
      message += 'Рекомендуется перескачать.'
    } else {
      message += 'Изменений не обнаружено.\nЛокальная версия актуальна.'
    }
    
    alert(message)
  } catch (err) {
    alert('Ошибка проверки: ' + err.message)
  }
}

async function checkSubdomainChanges(subdomain) {
  try {
    const response = await fetch(`/api/check-changes/${folderName.value}?subdomain=${encodeURIComponent(subdomain.name)}`)
    const result = await response.json()
    
    let message = `Проверка изменений: ${subdomain.name}\n\n`
    
    if (result.error) {
      message += `Ошибка: ${result.error}`
    } else if (result.has_changes) {
      message += 'ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ!\n\n'
      if (result.title_changed) {
        message += `Заголовок:\n  Локально: "${result.local_title}"\n  Онлайн: "${result.online_title}"\n\n`
      }
      if (result.local_hash && result.online_hash) {
        message += `MD5:\n  Локально: ${result.local_hash.substring(0, 8)}...\n  Онлайн: ${result.online_hash.substring(0, 8)}...\n\n`
      }
      message += 'Рекомендуется перескачать.'
    } else {
      message += 'Изменений не обнаружено.\nЛокальная версия актуальна.'
    }
    
    alert(message)
  } catch (err) {
    alert('Ошибка проверки: ' + err.message)
  }
}

async function setSubdomainTag(subdomain, tagId) {
  try {
    const newConfig = { ...subdomain.config, tag: tagId }
    const response = await fetch('/api/landings/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        config_key: subdomain.config_key,
        settings: newConfig
      })
    })
    
    if (response.ok) {
      const sub = siteData.value.subdomains.find(s => s.name === subdomain.name)
      if (sub) {
        if (!sub.config) sub.config = {}
        sub.config.tag = tagId
      }
    }
  } catch (err) {
    console.error('Ошибка сохранения тега:', err)
  }
}

async function toggleSubdomainExclude(subdomain) {
  const newExcluded = !subdomain.excluded
  
  try {
    const response = await fetch('/api/landings/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        config_key: subdomain.config_key,
        settings: { ...subdomain.config, excluded: newExcluded }
      })
    })
    
    if (response.ok) {
      // Обновляем данные в siteData напрямую
      const sub = siteData.value.subdomains.find(s => s.name === subdomain.name)
      if (sub) {
        if (!sub.config) sub.config = {}
        sub.config.excluded = newExcluded
      }
    }
  } catch (err) {
    console.error('Ошибка сохранения метки:', err)
  }
}

async function checkChanges() {
  try {
    const result = await landingsStore.checkChanges(folderName.value)
    
    // Сохраняем результат проверки
    lastCheck.value = {
      date: new Date(result.checked_at || Date.now()).toLocaleString('ru-RU'),
      has_changes: result.has_changes,
      details: result
    }
    
    let message = `Проверка изменений\n\n`
    message += `URL: ${result.url}\n`
    message += `Проверено: ${lastCheck.value.date}\n\n`
    
    if (result.has_changes) {
      message += '🔴 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ!\n\n'
      
      if (result.title_changed) {
        message += `Заголовок изменён:\n`
        message += `  Локально: "${result.local_title}"\n`
        message += `  Онлайн: "${result.online_title}"\n\n`
      }
      
      if (result.local_hash && result.online_hash) {
        message += `MD5 хеши:\n`
        message += `  Локально: ${result.local_hash.substring(0, 8)}...\n`
        message += `  Онлайн: ${result.online_hash.substring(0, 8)}...\n\n`
      }
      
      message += 'Рекомендуется перескачать сайт.'
    } else {
      message += '✅ Изменений не обнаружено\n\nЛокальная версия актуальна.'
    }
    
    alert(message)
  } catch (err) {
    alert('Ошибка проверки: ' + err.message)
  }
}

async function deleteSite() {
  if (!confirm(`Удалить "${siteData.value.domain}"?\n\nЭто действие нельзя отменить!`)) {
    return
  }
  
  try {
    await landingsStore.deleteFolder(folderName.value)
    router.push('/landings')
  } catch (err) {
    alert('Ошибка удаления: ' + err.message)
  }
}

onMounted(async () => {
  loadFolderTags()
  loadThumbnail()
  await loadSiteData()
  loadFileTree()
})
</script>
