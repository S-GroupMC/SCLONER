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
            <!-- Кнопка для prepared/scanned статусов -->
            <button 
              v-if="landingMeta?.status === 'prepared' || landingMeta?.status === 'scanned'"
              @click="continueDownloadWizard"
              class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg text-white bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 shadow-md hover:shadow-lg transition-all"
            >
              <i class="fas fa-play mr-2"></i>Продолжить скачивание
            </button>
            <button v-else @click="openInBrowser" class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg text-white bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 shadow-md hover:shadow-lg transition-all">
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
            <button @click="showHistoryLogs" class="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg text-gray-700 bg-gray-100 border border-gray-300 hover:bg-gray-200 shadow-sm hover:shadow transition-all">
              <i class="fas fa-terminal mr-2"></i>Логи
            </button>
            <button @click="deleteSite" class="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg text-red-700 bg-red-50 border border-red-200 hover:bg-red-100 shadow-sm hover:shadow transition-all">
              <i class="fas fa-trash mr-2"></i>Удалить
            </button>
          </div>
        </div>
      </div>
      
      <!-- Баннер для prepared/scanned статусов -->
      <div v-if="landingMeta?.status === 'prepared'" class="bg-gradient-to-r from-yellow-500 to-orange-500 rounded-xl shadow-lg p-5">
        <div class="flex items-center justify-between">
          <div class="flex items-center text-white">
            <div class="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center mr-4">
              <i class="fas fa-folder-open text-xl"></i>
            </div>
            <div>
              <h3 class="font-bold text-lg">Папка подготовлена</h3>
              <p class="text-white/80 text-sm">Контент ещё не скачан. Запустите анализ и выберите домены для скачивания.</p>
            </div>
          </div>
          <button 
            @click="continueDownloadWizard"
            class="px-6 py-3 bg-white text-orange-600 rounded-lg font-bold hover:bg-orange-50 transition-all shadow-lg"
          >
            <i class="fas fa-play mr-2"></i>Начать скачивание
          </button>
        </div>
      </div>
      
      <div v-else-if="landingMeta?.status === 'scanned'" class="bg-gradient-to-r from-purple-500 to-indigo-500 rounded-xl shadow-lg p-5">
        <div class="flex items-center justify-between">
          <div class="flex items-center text-white">
            <div class="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center mr-4">
              <i class="fas fa-search text-xl"></i>
            </div>
            <div>
              <h3 class="font-bold text-lg">Сайт проанализирован</h3>
              <p class="text-white/80 text-sm">
                Найдено {{ landingMeta.scan_result?.categories?.main?.length || 0 }} основных доменов. 
                Выберите что скачивать.
              </p>
            </div>
          </div>
          <button 
            @click="continueDownloadWizard"
            class="px-6 py-3 bg-white text-purple-600 rounded-lg font-bold hover:bg-purple-50 transition-all shadow-lg"
          >
            <i class="fas fa-download mr-2"></i>Выбрать и скачать
          </button>
        </div>
      </div>
      
      <!-- Активная загрузка (перекачивание) -->
      <div v-if="activeJob" class="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl shadow-lg p-5 relative">
        <!-- Кнопка закрытия -->
        <button 
          @click="activeJob = null"
          class="absolute top-3 right-3 w-8 h-8 bg-white/20 hover:bg-white/30 rounded-full flex items-center justify-center text-white/70 hover:text-white transition-all"
          title="Закрыть"
        >
          <i class="fas fa-times"></i>
        </button>
        
        <!-- Заголовок -->
        <div class="flex items-center justify-between mb-4 pr-10">
          <h3 class="text-white font-bold text-lg flex items-center">
            <div class="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center mr-3">
              <i class="fas fa-download" :class="activeJob.status === 'running' ? 'animate-bounce' : ''"></i>
            </div>
            {{ activeJob.status === 'completed' ? 'Скачивание завершено' : activeJob.status === 'failed' ? 'Ошибка скачивания' : 'Перекачивание сайта' }}
          </h3>
          <div class="flex items-center space-x-2">
            <button 
              @click="copyJobLogs"
              class="px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 text-sm font-medium transition-all"
              :title="logsCopied ? 'Скопировано!' : 'Скопировать логи'"
            >
              <i :class="logsCopied ? 'fas fa-check' : 'fas fa-copy'" class="mr-2"></i>{{ logsCopied ? 'Скопировано' : 'Копировать' }}
            </button>
            <button 
              @click="showLogsModal = true"
              class="px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 text-sm font-medium transition-all"
            >
              <i class="fas fa-terminal mr-2"></i>Логи ({{ activeJob.logs?.length || 0 }})
            </button>
            <button 
              v-if="activeJob.status === 'running'"
              @click="stopRedownload"
              class="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 text-sm font-medium transition-all"
            >
              <i class="fas fa-stop mr-2"></i>Остановить
            </button>
          </div>
        </div>
        
        <!-- Статистика -->
        <div class="grid grid-cols-4 gap-3 mb-4">
          <div class="bg-white/10 rounded-lg p-3 text-center">
            <div class="text-2xl font-bold text-white">{{ activeJob.files || 0 }}</div>
            <div class="text-xs text-white/60">Файлов</div>
          </div>
          <div class="bg-white/10 rounded-lg p-3 text-center">
            <div class="text-2xl font-bold text-white">{{ activeJob.size || '0 B' }}</div>
            <div class="text-xs text-white/60">Размер</div>
          </div>
          <div class="bg-white/10 rounded-lg p-3 text-center">
            <div class="text-2xl font-bold text-white">{{ activeJob.progress || 0 }}%</div>
            <div class="text-xs text-white/60">Прогресс</div>
          </div>
          <div class="bg-white/10 rounded-lg p-3 text-center">
            <div class="text-2xl font-bold text-white capitalize">{{ activeJob.status || 'running' }}</div>
            <div class="text-xs text-white/60">Статус</div>
          </div>
        </div>
        
        <!-- Прогресс-бар -->
        <div class="mb-4">
          <div class="flex justify-between text-xs text-white/70 mb-1">
            <span>Прогресс загрузки</span>
            <span>{{ activeJob.progress || 0 }}%</span>
          </div>
          <div class="w-full bg-black/30 rounded-full h-4 overflow-hidden">
            <div 
              class="h-4 rounded-full transition-all duration-500 relative overflow-hidden"
              :class="activeJob.progress >= 100 ? 'bg-green-500' : 'bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500'"
              :style="{ width: Math.max(activeJob.progress || 0, 2) + '%' }"
            >
              <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"></div>
            </div>
          </div>
        </div>
        
        <!-- Последние логи (живой вывод) -->
        <div class="bg-black/30 rounded-lg p-3">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-white/50 font-medium">
              <i class="fas fa-terminal mr-1"></i>Последние действия
            </span>
            <span class="text-xs text-white/40">{{ activeJob.logs?.length || 0 }} строк</span>
          </div>
          <div class="space-y-1 max-h-32 overflow-y-auto font-mono text-xs">
            <div 
              v-for="(line, idx) in (activeJob.logs || []).slice(-5)" 
              :key="idx"
              class="py-0.5 px-2 rounded"
              :class="getLogLineClass(line)"
            >
              {{ line }}
            </div>
            <div v-if="!activeJob.logs?.length" class="text-white/40 text-center py-2">
              Ожидание данных...
            </div>
          </div>
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
          
          <!-- Статус Node.js скриптов и Vue обёртки -->
          <div class="card">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-gray-700 flex items-center">
                <i class="fas fa-code mr-2 text-green-600"></i>
                Node.js / Vue обёртка
              </h3>
              <button 
                v-if="!scriptsStatus?.all_ready"
                @click="generateScripts" 
                :disabled="generatingScripts"
                class="text-xs px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
              >
                <i class="fas mr-1" :class="generatingScripts ? 'fa-spinner fa-spin' : 'fa-magic'"></i>
                Сгенерировать
              </button>
            </div>
            
            <div class="grid grid-cols-2 gap-2 text-xs">
              <!-- Vue Wrapper -->
              <div class="flex items-center space-x-2 p-2 rounded" :class="scriptsStatus?.vue_wrapper?.ready ? 'bg-green-50' : 'bg-gray-50'">
                <i class="fas" :class="scriptsStatus?.vue_wrapper?.ready ? 'fa-check-circle text-green-500' : 'fa-times-circle text-gray-400'"></i>
                <span :class="scriptsStatus?.vue_wrapper?.ready ? 'text-green-700' : 'text-gray-500'">Vue обёртка</span>
              </div>
              
              <!-- Backend Server -->
              <div class="flex items-center space-x-2 p-2 rounded" :class="scriptsStatus?.backend_server?.ready ? 'bg-green-50' : 'bg-gray-50'">
                <i class="fas" :class="scriptsStatus?.backend_server?.ready ? 'fa-check-circle text-green-500' : 'fa-times-circle text-gray-400'"></i>
                <span :class="scriptsStatus?.backend_server?.ready ? 'text-green-700' : 'text-gray-500'">Backend сервер</span>
              </div>
              
              <!-- Site Content -->
              <div class="flex items-center space-x-2 p-2 rounded" :class="scriptsStatus?.site_content?.ready ? 'bg-green-50' : 'bg-gray-50'">
                <i class="fas" :class="scriptsStatus?.site_content?.ready ? 'fa-check-circle text-green-500' : 'fa-times-circle text-gray-400'"></i>
                <span :class="scriptsStatus?.site_content?.ready ? 'text-green-700' : 'text-gray-500'">Контент (_site)</span>
              </div>
              
              <!-- NPM Installed -->
              <div class="flex items-center space-x-2 p-2 rounded" :class="scriptsStatus?.vue_wrapper?.npm_installed ? 'bg-green-50' : 'bg-yellow-50'">
                <i class="fas" :class="scriptsStatus?.vue_wrapper?.npm_installed ? 'fa-check-circle text-green-500' : 'fa-exclamation-circle text-yellow-500'"></i>
                <span :class="scriptsStatus?.vue_wrapper?.npm_installed ? 'text-green-700' : 'text-yellow-600'">npm install</span>
              </div>
            </div>
            
            <!-- Инструкции по запуску -->
            <div v-if="scriptsStatus?.all_ready" class="mt-3 p-2 bg-blue-50 rounded text-xs">
              <div class="font-medium text-blue-700 mb-1">Запуск:</div>
              <code class="block text-blue-600 font-mono">cd {{ folderName }}/vue-app && npm run dev</code>
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
            @click="activeTab = 'trackers'; if (!trackersData) loadTrackers()"
            class="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center space-x-2"
            :class="activeTab === 'trackers' ? 'border-yellow-600 text-yellow-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
          >
            <i class="fas fa-bug"></i>
            <span>Трекеры</span>
            <span v-if="trackersData?.total_trackers > 0" class="ml-1 px-1.5 py-0.5 text-xs rounded-full" :class="activeTab === 'trackers' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-600'">{{ trackersData.total_trackers }}</span>
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
            <button 
              @click="checkIntegrity" 
              :disabled="integrityLoading" 
              class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg text-white bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 disabled:opacity-50 shadow-sm transition-all" 
              title="Найти пропущенные CSS, JS, картинки и шрифты"
            >
              <i class="fas mr-1.5" :class="integrityLoading ? 'fa-spinner fa-spin' : 'fa-stethoscope'"></i>
              Проверить целостность
            </button>
            <button 
              @click="loadFileTree" 
              class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 shadow-sm transition-all" 
              title="Обновить список файлов"
            >
              <i class="fas fa-sync-alt mr-1.5"></i>Обновить
            </button>
            <button 
              @click="toggleAllFolders" 
              class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 shadow-sm transition-all"
              title="Развернуть или свернуть все папки"
            >
              <i class="fas fa-expand-arrows-alt mr-1.5"></i>{{ allExpanded ? 'Свернуть всё' : 'Развернуть всё' }}
            </button>
          </div>
        </div>
        
        <!-- Статистика по типам файлов -->
        <div v-if="fileTreeStats" class="grid grid-cols-6 gap-2 mb-4">
          <div class="bg-orange-50 rounded-lg px-3 py-2 text-center border border-orange-100">
            <div class="text-xl font-bold text-orange-700">{{ fileTreeStats.html }}</div>
            <div class="text-xs text-orange-600 font-medium">HTML</div>
          </div>
          <div class="bg-blue-50 rounded-lg px-3 py-2 text-center border border-blue-100">
            <div class="text-xl font-bold text-blue-700">{{ fileTreeStats.css }}</div>
            <div class="text-xs text-blue-600 font-medium">CSS</div>
          </div>
          <div class="bg-yellow-50 rounded-lg px-3 py-2 text-center border border-yellow-100">
            <div class="text-xl font-bold text-yellow-700">{{ fileTreeStats.js }}</div>
            <div class="text-xs text-yellow-600 font-medium">JS</div>
          </div>
          <div class="bg-green-50 rounded-lg px-3 py-2 text-center border border-green-100">
            <div class="text-xl font-bold text-green-700">{{ fileTreeStats.images }}</div>
            <div class="text-xs text-green-600 font-medium">Картинки</div>
          </div>
          <div class="bg-gray-50 rounded-lg px-3 py-2 text-center border border-gray-200">
            <div class="text-xl font-bold text-gray-700">{{ fileTreeStats.other }}</div>
            <div class="text-xs text-gray-600 font-medium">Другое</div>
          </div>
          <div class="rounded-lg px-3 py-2 text-center border" :class="integrityResult?.total_missing > 0 ? 'bg-red-50 border-red-200' : 'bg-emerald-50 border-emerald-200'">
            <div class="text-xl font-bold" :class="integrityResult?.total_missing > 0 ? 'text-red-600' : 'text-emerald-600'">
              {{ integrityResult?.total_missing || 0 }}
            </div>
            <div class="text-xs font-medium" :class="integrityResult?.total_missing > 0 ? 'text-red-500' : 'text-emerald-500'">
              Не скачано
            </div>
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
                    <td class="px-2 py-1 text-gray-600 truncate max-w-xs" :title="item.referenced_by?.join(', ') || ''">{{ item.referenced_by?.[0] || '-' }}{{ (item.referenced_by?.length || 0) > 1 ? ` (+${item.referenced_by.length - 1})` : '' }}</td>
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
          <!-- Заголовок таблицы -->
          <div class="flex items-center px-3 py-2 bg-gray-100 border-b border-gray-200 text-xs font-semibold text-gray-600 uppercase tracking-wider">
            <div class="w-56 flex-shrink-0 pl-6">Папка / Файл</div>
            <div class="w-20 flex-shrink-0 px-1 text-center">Тег</div>
            <div class="w-20 text-center flex-shrink-0">Файлов</div>
            <div class="w-20 text-right flex-shrink-0">Размер</div>
            <div class="w-16 text-center flex-shrink-0">HTML</div>
            <div class="w-24 flex-shrink-0 px-2 text-center">Прогресс</div>
            <div class="flex-shrink-0 ml-auto text-right">Действия</div>
          </div>
          <div class="divide-y divide-gray-100">
            <template v-for="node in fileTree.children" :key="node.path">
              <!-- Папка -->
              <div v-if="node.isDir">
                <div 
                  @click="toggleFolder(node.path)"
                  class="flex items-center px-3 py-2.5 bg-gray-50 hover:bg-gray-100 cursor-pointer select-none transition-colors border-b border-gray-100"
                  :style="{ paddingLeft: (node.depth * 16 + 12) + 'px' }"
                >
                  <!-- Левая часть: иконка и название -->
                  <div class="flex items-center space-x-2 min-w-0 w-56 flex-shrink-0">
                    <i class="fas text-xs transition-transform w-3" :class="expandedFolders[node.path] ? 'fa-chevron-down text-gray-500' : 'fa-chevron-right text-gray-400'"></i>
                    <i class="fas fa-folder text-sm" :class="expandedFolders[node.path] ? 'fa-folder-open text-yellow-500' : 'fa-folder text-yellow-400'"></i>
                    <span class="text-sm font-semibold text-gray-700 truncate">{{ node.name }}</span>
                  </div>
                  
                  <!-- Тег -->
                  <div class="w-20 flex-shrink-0 px-1" @click.stop>
                    <select 
                      :value="folderTags[node.path] || ''"
                      @change="setFolderTag(node.path, $event.target.value)"
                      class="text-xs border rounded px-1 py-0.5 cursor-pointer w-full"
                      :class="getFolderTagInfo(folderTags[node.path]).color"
                    >
                      <option v-for="t in folderTagOptions" :key="t.id" :value="t.id">{{ t.label }}</option>
                    </select>
                  </div>
                  
                  <!-- Статистика: файлы -->
                  <div class="w-20 text-center flex-shrink-0">
                    <span class="text-xs font-medium text-gray-600">{{ node.fileCount }}</span>
                    <span class="text-xs text-gray-400 ml-0.5">файлов</span>
                  </div>
                  
                  <!-- Размер -->
                  <div class="w-20 text-right flex-shrink-0">
                    <span class="text-xs font-mono font-medium text-gray-700">{{ node.sizeFormatted }}</span>
                  </div>
                  
                  <!-- HTML страниц -->
                  <div class="w-16 text-center flex-shrink-0">
                    <span v-if="node.htmlCount > 0" class="text-xs font-medium px-1.5 py-0.5 rounded bg-orange-100 text-orange-700">{{ node.htmlCount }} html</span>
                    <span v-else class="text-xs text-gray-300">—</span>
                  </div>
                  
                  <!-- Прогресс-бар (заглушка - 100% если есть файлы) -->
                  <div class="w-24 flex-shrink-0 px-2">
                    <div class="w-full bg-gray-200 rounded-full h-1.5">
                      <div class="bg-green-500 h-1.5 rounded-full" style="width: 100%"></div>
                    </div>
                  </div>
                  
                  <!-- Кнопки действий -->
                  <div class="flex items-center space-x-1 flex-shrink-0 ml-auto" @click.stop>
                    <a 
                      :href="'/api/browse/' + folderName + '/' + node.path + '/'" 
                      target="_blank" 
                      class="p-1.5 rounded hover:bg-blue-100 text-blue-500 hover:text-blue-700 transition-colors" 
                      title="Открыть папку в браузере"
                    ><i class="fas fa-external-link-alt text-xs"></i></a>
                    <a 
                      v-if="node.name.includes('.')" 
                      :href="'https://' + node.name" 
                      target="_blank" 
                      class="p-1.5 rounded hover:bg-green-100 text-green-500 hover:text-green-700 transition-colors" 
                      title="Открыть оригинал онлайн"
                    ><i class="fas fa-globe text-xs"></i></a>
                    <button 
                      @click="checkFolderChanges(node)" 
                      class="p-1.5 rounded hover:bg-purple-100 text-purple-500 hover:text-purple-700 transition-colors" 
                      title="Проверить изменения на сайте"
                    ><i class="fas fa-search text-xs"></i></button>
                    <button 
                      @click="redownloadFolder(node)" 
                      class="p-1.5 rounded hover:bg-orange-100 text-orange-500 hover:text-orange-700 transition-colors" 
                      title="Перескачать эту папку"
                    ><i class="fas fa-sync-alt text-xs"></i></button>
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
      
      <!-- ТАБ: Трекеры -->
      <div v-show="activeTab === 'trackers'" class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold text-gray-900 flex items-center">
            <i class="fas fa-bug mr-2 text-yellow-600"></i>
            Найденные трекеры
          </h2>
          <button 
            @click="loadTrackers()"
            :disabled="trackersLoading"
            class="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 text-sm font-medium transition-all disabled:opacity-50"
          >
            <i :class="trackersLoading ? 'fas fa-spinner fa-spin' : 'fas fa-search'" class="mr-2"></i>
            {{ trackersLoading ? 'Сканирование...' : 'Сканировать' }}
          </button>
        </div>
        
        <!-- Загрузка -->
        <div v-if="trackersLoading" class="flex items-center justify-center py-12">
          <i class="fas fa-spinner fa-spin text-3xl text-yellow-500 mr-3"></i>
          <span class="text-gray-500">Сканирование HTML файлов...</span>
        </div>
        
        <!-- Результаты -->
        <div v-else-if="trackersData">
          <!-- Сводка -->
          <div class="grid grid-cols-3 gap-4 mb-6">
            <div class="bg-gray-50 rounded-lg p-4 text-center">
              <div class="text-2xl font-bold" :class="trackersData.total_trackers > 0 ? 'text-red-600' : 'text-green-600'">{{ trackersData.total_trackers }}</div>
              <div class="text-xs text-gray-500 mt-1">Трекеров найдено</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
              <div class="text-2xl font-bold text-gray-700">{{ trackersData.files_with_trackers }}</div>
              <div class="text-xs text-gray-500 mt-1">Файлов с трекерами</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
              <div class="text-2xl font-bold text-gray-700">{{ trackersData.total_files_scanned }}</div>
              <div class="text-xs text-gray-500 mt-1">HTML файлов проверено</div>
            </div>
          </div>
          
          <!-- Сводка по типам -->
          <div v-if="Object.keys(trackersData.summary || {}).length > 0" class="mb-6">
            <h3 class="text-sm font-semibold text-gray-700 mb-3">По типам:</h3>
            <div class="flex flex-wrap gap-2">
              <span 
                v-for="(count, type) in trackersData.summary" 
                :key="type"
                class="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium"
                :class="trackerTypeColor(type)"
              >
                <i class="fas fa-exclamation-triangle mr-1.5"></i>
                {{ type }} <span class="ml-1 font-bold">x{{ count }}</span>
              </span>
            </div>
          </div>
          
          <!-- Список трекеров -->
          <div v-if="trackersData.trackers?.length > 0" class="space-y-3">
            <h3 class="text-sm font-semibold text-gray-700 mb-2">Детали:</h3>
            <div 
              v-for="(tracker, idx) in trackersData.trackers" 
              :key="idx"
              class="border rounded-lg p-3 hover:border-yellow-300 transition-colors"
            >
              <div class="flex items-start justify-between mb-2">
                <div class="flex items-center space-x-2">
                  <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium" :class="trackerTypeColor(tracker.type)">
                    {{ tracker.type }}
                  </span>
                  <span class="text-xs text-gray-400">{{ tracker.size }} bytes</span>
                </div>
              </div>
              <div class="flex items-center text-xs text-gray-500 mb-2">
                <i class="fas fa-file-code mr-1.5"></i>
                <span class="font-mono">{{ tracker.file }}</span>
                <span class="mx-1.5">:</span>
                <span class="text-gray-400">line {{ tracker.line }}</span>
              </div>
              <div class="bg-gray-900 rounded p-2 overflow-x-auto">
                <code class="text-xs text-green-400 font-mono whitespace-pre-wrap break-all">{{ tracker.snippet }}</code>
              </div>
            </div>
          </div>
          
          <!-- Нет трекеров -->
          <div v-else class="bg-green-50 rounded-lg p-8 text-center">
            <i class="fas fa-check-circle text-4xl text-green-500 mb-3"></i>
            <p class="text-green-700 font-medium">Трекеры не найдены!</p>
            <p class="text-green-600 text-sm mt-1">Сайт чист от известных трекеров</p>
          </div>
        </div>
        
        <!-- Пустое состояние -->
        <div v-else class="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
          <i class="fas fa-bug text-4xl mb-3"></i>
          <p>Нажмите "Сканировать" для поиска трекеров в HTML файлах</p>
          <p class="text-xs mt-2">Google Analytics, Facebook Pixel, Hotjar, Shopify Analytics и др.</p>
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
    
    <!-- Модальное окно выбора платформы -->
    <div v-if="showEngineModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showEngineModal = false">
      <div class="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold text-gray-900">
            <i class="fas fa-download mr-2 text-orange-500"></i>Перекачать сайт
          </h3>
          <button @click="showEngineModal = false" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <p class="text-sm text-gray-600 mb-4">Выберите платформу для скачивания:</p>
        
        <div class="grid grid-cols-2 gap-3 mb-6">
          <label 
            v-for="engine in engines" 
            :key="engine.value"
            class="relative flex flex-col items-center justify-center p-4 border-2 rounded-lg cursor-pointer transition-all"
            :class="selectedEngine === engine.value 
              ? 'border-blue-500 bg-blue-50' 
              : 'border-gray-200 hover:border-gray-300'"
          >
            <input 
              type="radio" 
              v-model="selectedEngine" 
              :value="engine.value"
              class="sr-only"
            />
            <i :class="engine.icon" class="text-3xl mb-2" :style="{ color: engine.color }"></i>
            <div class="font-medium text-sm">{{ engine.label }}</div>
            <div class="text-xs text-gray-500 mt-1 text-center">{{ engine.desc }}</div>
          </label>
        </div>
        
        <div class="flex space-x-3">
          <button 
            @click="showEngineModal = false" 
            class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
          >
            Отмена
          </button>
          <button 
            @click="confirmRedownload" 
            class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-white bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 transition-all"
          >
            <i class="fas fa-download mr-2"></i>Перекачать
          </button>
        </div>
      </div>
    </div>
    
    <!-- Модальное окно открытия сайта -->
    <div v-if="showOpenModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showOpenModal = false">
      <div class="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold text-gray-900">
            <i class="fas fa-external-link-alt mr-2 text-blue-500"></i>Открыть сайт
          </h3>
          <button @click="showOpenModal = false" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <p class="text-sm text-gray-600 mb-4">
          Выберите как открыть сайт:
        </p>
        
        <!-- Опции открытия -->
        <div class="space-y-3 mb-4">
          <button 
            @click="openStaticHtml"
            class="w-full flex items-start p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left"
          >
            <i class="fas fa-file-code text-xl text-orange-500 mr-3 mt-0.5"></i>
            <div>
              <div class="font-medium text-gray-900">Статичный HTML</div>
              <div class="text-xs text-gray-500 mt-1">
                Открыть index.html напрямую (быстро, без сервера)
              </div>
            </div>
          </button>
          
          <button 
            @click="openVueWrapper"
            :disabled="!scriptsStatus?.vue_wrapper?.ready || startingServer === 'vue'"
            class="w-full flex items-start p-3 border rounded-lg transition-colors text-left"
            :class="scriptsStatus?.vue_wrapper?.ready ? 'border-green-200 hover:bg-green-50' : 'border-gray-200 opacity-50 cursor-not-allowed'"
          >
            <div class="relative mr-3 mt-0.5">
              <i v-if="startingServer === 'vue'" class="fas fa-spinner fa-spin text-xl text-green-500"></i>
              <i v-else class="fab fa-vuejs text-xl text-green-500"></i>
              <span v-if="runningServers.vue" class="absolute -top-1 -right-1 w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse" title="Сервер запущен"></span>
            </div>
            <div class="flex-1">
              <div class="font-medium text-gray-900 flex items-center">
                Vue + Node.js сервер
                <span v-if="startingServer === 'vue'" class="ml-2 text-xs text-yellow-600 font-normal">
                  <i class="fas fa-spinner fa-spin"></i> Запуск...
                </span>
                <span v-else-if="runningServers.vue" class="ml-2 text-xs text-green-600 font-normal">
                  <i class="fas fa-play-circle"></i> :{{ runningServers.vue.port }}
                </span>
                <span v-else-if="scriptsStatus?.vue_wrapper?.ready" class="ml-2 text-xs text-green-600">
                  <i class="fas fa-check-circle"></i> Готово
                </span>
                <span v-else class="ml-2 text-xs text-gray-400">
                  <i class="fas fa-times-circle"></i> Не создано
                </span>
              </div>
              <div class="text-xs text-gray-500 mt-1">
                SPA с роутингом, SEO и CORS сервер
              </div>
            </div>
            <!-- Кнопка перезапуска Vue сервера -->
            <button 
              v-if="runningServers.vue"
              @click.stop="restartVueServer"
              :disabled="restartingVue"
              class="ml-2 px-2 py-1 text-xs rounded bg-yellow-100 hover:bg-yellow-200 text-yellow-700 transition-colors"
              title="Перезапустить сервер"
            >
              <i :class="restartingVue ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i>
            </button>
          </button>
        </div>
        
        <!-- Прогресс запуска серверов -->
        <div v-if="serverLaunchSteps.length > 0" class="border-t pt-4 mt-2">
          <h4 class="text-xs font-semibold text-gray-500 uppercase mb-2">
            <i class="fas fa-terminal mr-1"></i> Процесс запуска
          </h4>
          <div class="space-y-1.5 max-h-48 overflow-y-auto">
            <div 
              v-for="(s, idx) in serverLaunchSteps" 
              :key="idx"
              class="flex items-start text-xs font-mono px-2 py-1 rounded"
              :class="{
                'bg-green-50 text-green-700': s.status === 'ok',
                'bg-red-50 text-red-700': s.status === 'error',
                'bg-yellow-50 text-yellow-700': s.status === 'warn' || s.status === 'running',
                'bg-gray-50 text-gray-500': s.status === 'skip'
              }"
            >
              <span class="w-4 mr-2 flex-shrink-0 text-center">
                <i v-if="s.status === 'ok'" class="fas fa-check text-green-500"></i>
                <i v-else-if="s.status === 'error'" class="fas fa-times text-red-500"></i>
                <i v-else-if="s.status === 'warn'" class="fas fa-exclamation text-yellow-500"></i>
                <i v-else-if="s.status === 'running'" class="fas fa-spinner fa-spin text-yellow-500"></i>
                <i v-else class="fas fa-minus text-gray-400"></i>
              </span>
              <span class="font-semibold mr-2 flex-shrink-0" style="min-width: 120px">{{ stepLabel(s.name) }}</span>
              <span class="text-gray-500 truncate" :title="s.detail">{{ s.detail }}</span>
            </div>
            <!-- Spinner для текущего шага -->
            <div v-if="startingServer === 'vue' && !serverLaunchError" class="flex items-center text-xs font-mono px-2 py-1 bg-blue-50 text-blue-600 rounded">
              <i class="fas fa-spinner fa-spin mr-2"></i>
              <span>Ожидание ответа сервера...</span>
            </div>
          </div>
          
          <!-- Ошибка -->
          <div v-if="serverLaunchError" class="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
            <i class="fas fa-exclamation-triangle mr-1"></i>
            {{ serverLaunchError }}
          </div>
          
          <!-- Успех + Кнопки -->
          <div v-if="!startingServer && !serverLaunchError && serverLaunchSteps.length > 0 && serverLaunchSteps[serverLaunchSteps.length - 1]?.status === 'ok'" class="mt-3">
            <div class="p-2 bg-green-50 border border-green-200 rounded text-xs text-green-700 flex items-center">
              <i class="fas fa-check-circle mr-1"></i> Серверы запущены успешно
            </div>
            <div class="mt-2 flex gap-2">
              <button 
                @click="openVueSite"
                class="flex-1 px-4 py-2.5 text-sm font-semibold rounded-lg text-white bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2"
              >
                <i class="fas fa-external-link-alt"></i> Открыть сайт
              </button>
              <button 
                @click="restartAndRecheck"
                :disabled="startingServer === 'restarting'"
                class="px-4 py-2.5 text-sm font-semibold rounded-lg text-white bg-gradient-to-r from-orange-400 to-red-500 hover:from-orange-500 hover:to-red-600 shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <i :class="startingServer === 'restarting' ? 'fas fa-spinner fa-spin' : 'fas fa-redo'"></i> Перезапустить
              </button>
            </div>
          </div>
          
          <!-- Копировать логи -->
          <div class="mt-2 flex justify-end">
            <button 
              @click="copyLaunchLogs"
              class="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              title="Скопировать логи запуска"
            >
              <i class="fas fa-copy mr-1"></i> Копировать логи
            </button>
          </div>
        </div>
        
        <!-- Кнопка генерации если ничего не готово -->
        <div v-if="!scriptsStatus?.vue_wrapper?.ready && !scriptsStatus?.backend_server?.ready" class="border-t pt-4">
          <button 
            @click="showOpenModal = false; generateScripts()"
            class="w-full px-4 py-2 text-sm font-medium rounded-lg text-white bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 transition-all"
          >
            <i class="fas fa-magic mr-2"></i>Сгенерировать скрипты
          </button>
        </div>
      </div>
    </div>
    
    <!-- Модальное окно Backend сервера -->
    <div v-if="showBackendModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showBackendModal = false">
      <div class="bg-white rounded-xl shadow-2xl p-6 w-full max-w-lg mx-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold text-gray-900">
            <i class="fab fa-node-js mr-2 text-green-600"></i>Запуск Backend сервера
          </h3>
          <button @click="showBackendModal = false" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <p class="text-sm text-gray-600 mb-4">
          Запустите Node.js сервер для статики в терминале:
        </p>
        
        <div class="bg-gray-900 rounded-lg p-4 mb-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-gray-400">Терминал</span>
            <button @click="copyBackendCommand" class="text-xs text-blue-400 hover:text-blue-300">
              <i class="fas fa-copy mr-1"></i>Копировать
            </button>
          </div>
          <code class="text-green-400 font-mono text-sm block">cd {{ siteData.path }}</code>
          <code class="text-green-400 font-mono text-sm block mt-1">node backend-server.js</code>
        </div>
        
        <div class="bg-blue-50 rounded-lg p-3 mb-4">
          <div class="text-sm text-blue-800">
            <i class="fas fa-info-circle mr-2"></i>
            После запуска откройте: <strong>http://localhost:{{ config.defaultBackendPort }}</strong>
          </div>
        </div>
        
        <div class="flex space-x-3">
          <button 
            @click="showBackendModal = false" 
            class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
          >
            Закрыть
          </button>
          <button 
            @click="copyBackendCommand(); showBackendModal = false"
            class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors"
          >
            <i class="fas fa-copy mr-2"></i>Копировать и закрыть
          </button>
        </div>
      </div>
    </div>
    
    <!-- Модальное окно npm install -->
    <div v-if="showNpmInstallModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showNpmInstallModal = false">
      <div class="bg-white rounded-xl shadow-2xl p-6 w-full max-w-lg mx-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold text-gray-900">
            <i class="fas fa-terminal mr-2 text-yellow-500"></i>Требуется npm install
          </h3>
          <button @click="showNpmInstallModal = false" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <p class="text-sm text-gray-600 mb-4">
          Для запуска Vue обёртки необходимо установить зависимости. Выполните команды в терминале:
        </p>
        
        <div class="bg-gray-900 rounded-lg p-4 mb-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-gray-400">Терминал</span>
            <button @click="copyNpmCommand" class="text-xs text-blue-400 hover:text-blue-300">
              <i class="fas fa-copy mr-1"></i>Копировать
            </button>
          </div>
          <code class="text-green-400 font-mono text-sm block">cd {{ siteData.path }}/vue-app</code>
          <code class="text-green-400 font-mono text-sm block mt-1">npm install</code>
          <code class="text-green-400 font-mono text-sm block mt-1">npm run dev</code>
        </div>
        
        <div class="flex space-x-3">
          <button 
            @click="showNpmInstallModal = false" 
            class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
          >
            Закрыть
          </button>
          <button 
            @click="copyNpmCommand(); showNpmInstallModal = false"
            class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors"
          >
            <i class="fas fa-copy mr-2"></i>Копировать и закрыть
          </button>
        </div>
      </div>
    </div>
    
    <!-- Модальное окно генерации скриптов -->
    <div v-if="showScriptsModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showScriptsModal = false">
      <div class="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold text-gray-900">
            <i class="fas fa-code mr-2 text-green-500"></i>Генерация скриптов
          </h3>
          <button @click="showScriptsModal = false" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <p class="text-sm text-gray-600 mb-4">
          Выберите что сгенерировать для запуска сайта:
        </p>
        
        <!-- Опции генерации -->
        <div class="space-y-3 mb-6">
          <label class="flex items-start p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors" :class="scriptsOptions.vueWrapper ? 'border-green-500 bg-green-50' : 'border-gray-200'">
            <input type="checkbox" v-model="scriptsOptions.vueWrapper" class="mt-0.5 mr-3">
            <div>
              <div class="font-medium text-gray-900 flex items-center">
                <i class="fab fa-vuejs mr-2 text-green-500"></i>Vue обёртка
              </div>
              <div class="text-xs text-gray-500 mt-1">
                SPA приложение с iframe, SEO-оптимизация, роутинг
              </div>
            </div>
          </label>
          
          <label class="flex items-start p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors" :class="scriptsOptions.backendServer ? 'border-blue-500 bg-blue-50' : 'border-gray-200'">
            <input type="checkbox" v-model="scriptsOptions.backendServer" class="mt-0.5 mr-3">
            <div>
              <div class="font-medium text-gray-900 flex items-center">
                <i class="fab fa-node-js mr-2 text-green-600"></i>Backend сервер
              </div>
              <div class="text-xs text-gray-500 mt-1">
                Node.js сервер для статики, CORS, проксирование
              </div>
            </div>
          </label>
          
          <label class="flex items-start p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors" :class="scriptsOptions.moveToSite ? 'border-purple-500 bg-purple-50' : 'border-gray-200'">
            <input type="checkbox" v-model="scriptsOptions.moveToSite" class="mt-0.5 mr-3">
            <div>
              <div class="font-medium text-gray-900 flex items-center">
                <i class="fas fa-folder-open mr-2 text-yellow-500"></i>Переместить в _site
              </div>
              <div class="text-xs text-gray-500 mt-1">
                Переместить скачанный контент в папку _site
              </div>
            </div>
          </label>
        </div>
        
        <!-- Порт -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">Порт сервера</label>
          <input type="number" v-model="scriptsOptions.port" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-green-500 focus:border-green-500">
        </div>
        
        <div class="flex space-x-3">
          <button 
            @click="showScriptsModal = false" 
            class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
          >
            Отмена
          </button>
          <button 
            @click="confirmGenerateScripts" 
            :disabled="generatingScripts || (!scriptsOptions.vueWrapper && !scriptsOptions.backendServer)"
            class="flex-1 px-4 py-2 text-sm font-medium rounded-lg text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            <i class="fas mr-2" :class="generatingScripts ? 'fa-spinner fa-spin' : 'fa-magic'"></i>
            Сгенерировать
          </button>
        </div>
      </div>
    </div>
    
    <!-- Модальное окно логов -->
    <div v-if="showLogsModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showLogsModal = false">
      <div class="bg-gray-900 rounded-xl shadow-2xl p-4 w-full max-w-4xl mx-4 max-h-[80vh] flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-lg font-bold text-white flex items-center">
            <i class="fas fa-terminal mr-2 text-green-400"></i>Логи загрузки
          </h3>
          <div class="flex items-center space-x-2">
            <button 
              @click="copyLogs" 
              class="px-3 py-1.5 text-xs font-medium rounded text-white bg-blue-600 hover:bg-blue-700 transition-colors"
            >
              <i class="fas fa-copy mr-1"></i>{{ logsCopied ? 'Скопировано!' : 'Копировать' }}
            </button>
            <button @click="showLogsModal = false" class="text-gray-400 hover:text-white">
              <i class="fas fa-times text-lg"></i>
            </button>
          </div>
        </div>
        
        <div 
          ref="logsContainer"
          class="flex-1 overflow-y-auto bg-black rounded-lg p-3 font-mono text-xs text-green-400 min-h-[300px] max-h-[60vh]"
        >
          <div v-for="(line, index) in currentLogs" :key="index" class="py-0.5 hover:bg-white/5">
            <span class="text-gray-500 mr-2 select-none">{{ String(index + 1).padStart(4, ' ') }}</span>
            <span :class="getLogLineClass(line)">{{ line }}</span>
          </div>
          <div v-if="!currentLogs.length" class="text-gray-500 text-center py-10">
            Логи пока пусты...
          </div>
        </div>
        
        <div class="mt-3 flex items-center justify-between text-xs text-gray-400">
          <span>Строк: {{ currentLogs.length }}</span>
          <label class="flex items-center cursor-pointer">
            <input type="checkbox" v-model="autoScrollLogs" class="mr-1.5">
            Автопрокрутка
          </label>
        </div>
      </div>
    </div>
    
    <!-- Модальное окно wizard скачивания - ВЫНЕСЕНО за пределы v-else -->
    <Teleport to="body">
      <div v-if="showDownloadWizard" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="closeWizard">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col" @click.stop>
          <!-- Header -->
          <div class="flex items-center justify-between p-5 border-b">
            <h3 class="text-lg font-bold text-gray-900 flex items-center">
              <i class="fas fa-download mr-2 text-blue-500"></i>
              {{ wizardStep === 1 ? 'Анализ сайта' : wizardStep === 2 ? 'Выбор доменов' : 'Скачивание' }}
            </h3>
            <button @click="closeWizard" class="text-gray-400 hover:text-gray-600">
              <i class="fas fa-times text-lg"></i>
            </button>
          </div>
          
          <!-- Step 1: Scanning -->
          <div v-if="wizardStep === 1" class="p-5 flex-1 overflow-y-auto">
            <div class="bg-gray-50 rounded-lg p-6 text-center">
              <div class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <i class="fas fa-search text-2xl text-blue-600 animate-pulse"></i>
              </div>
              <h4 class="text-lg font-bold text-gray-900 mb-2">Анализируем сайт...</h4>
              <p class="text-sm text-gray-600 mb-4">Ищем поддомены и ресурсы</p>
              
              <div class="w-full bg-gray-200 rounded-full h-3 mb-2">
                <div 
                  class="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-300"
                  :style="{ width: scanProgress + '%' }"
                ></div>
              </div>
              <div class="text-sm text-gray-500">
                {{ scanProgress }}% — {{ scanPagesScanned }} страниц просканировано
              </div>
            </div>
          </div>
          
          <!-- Step 2: Select Domains -->
          <div v-else-if="wizardStep === 2" class="p-5 flex-1 overflow-y-auto">
            <!-- Quick stats -->
            <div class="grid grid-cols-4 gap-3 mb-4">
              <div class="bg-green-50 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-green-600">{{ scanResult?.categories?.main?.length || 0 }}</div>
                <div class="text-xs text-green-700">Основные</div>
              </div>
              <div class="bg-blue-50 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-blue-600">{{ scanResult?.categories?.related?.length || 0 }}</div>
                <div class="text-xs text-blue-700">Связанные</div>
              </div>
              <div class="bg-yellow-50 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-yellow-600">{{ scanResult?.categories?.cdn?.length || 0 }}</div>
                <div class="text-xs text-yellow-700">CDN</div>
              </div>
              <div class="bg-gray-50 rounded-lg p-3 text-center">
                <div class="text-xl font-bold text-gray-600">{{ scanResult?.categories?.external?.length || 0 }}</div>
                <div class="text-xs text-gray-700">Внешние</div>
              </div>
            </div>
            
            <!-- Quick actions -->
            <div class="flex items-center justify-between bg-gray-50 rounded-lg p-3 mb-4">
              <div class="text-sm text-gray-600">
                Выбрано: <span class="font-bold text-blue-600">{{ selectedDomainsCount }}</span>
              </div>
              <div class="flex space-x-2 text-sm">
                <button @click="selectAllDomains('main')" class="text-green-600 hover:underline">Все основные</button>
                <button @click="selectAllDomains('cdn')" class="text-yellow-600 hover:underline">+ CDN</button>
                <button @click="deselectAllDomains" class="text-gray-500 hover:underline">Сбросить</button>
              </div>
            </div>
            
            <!-- Domain lists -->
            <div class="space-y-3 max-h-[40vh] overflow-y-auto">
              <!-- Main domains -->
              <div v-if="scanResult?.categories?.main?.length" class="border rounded-lg overflow-hidden">
                <div class="bg-green-50 px-3 py-2 border-b flex items-center justify-between">
                  <span class="font-medium text-green-800 text-sm">
                    <i class="fas fa-globe mr-1"></i>Основные ({{ scanResult.categories.main.length }})
                  </span>
                  <label class="flex items-center cursor-pointer text-xs">
                    <input type="checkbox" :checked="allDomainsSelected('main')" @change="toggleDomainCategory('main')" class="mr-1">
                    Все
                  </label>
                </div>
                <div class="divide-y max-h-32 overflow-y-auto">
                  <div v-for="d in scanResult.categories.main" :key="d.domain" class="flex items-center px-3 py-2 hover:bg-gray-50 text-sm">
                    <input type="checkbox" v-model="selectedDomains[d.domain]" class="mr-2">
                    <span class="flex-1">{{ d.domain }}</span>
                    <span v-if="d.is_main" class="px-1.5 py-0.5 text-xs bg-green-100 text-green-700 rounded mr-2">Главный</span>
                    <select 
                      v-model="domainEngines[d.domain]" 
                      class="text-xs border rounded px-1 py-0.5 mr-2 bg-white"
                      @click.stop
                    >
                      <option v-for="e in engines" :key="e.value" :value="e.value">{{ e.label }}</option>
                    </select>
                    <span class="text-xs text-gray-400">{{ d.count }}</span>
                  </div>
                </div>
              </div>
              
              <!-- CDN domains -->
              <div v-if="scanResult?.categories?.cdn?.length" class="border rounded-lg overflow-hidden">
                <div class="bg-yellow-50 px-3 py-2 border-b flex items-center justify-between">
                  <span class="font-medium text-yellow-800 text-sm">
                    <i class="fas fa-cloud mr-1"></i>CDN ({{ scanResult.categories.cdn.length }})
                  </span>
                  <label class="flex items-center cursor-pointer text-xs">
                    <input type="checkbox" :checked="allDomainsSelected('cdn')" @change="toggleDomainCategory('cdn')" class="mr-1">
                    Все
                  </label>
                </div>
                <div class="divide-y max-h-24 overflow-y-auto">
                  <div v-for="d in scanResult.categories.cdn" :key="d.domain" class="flex items-center px-3 py-2 hover:bg-gray-50 text-sm">
                    <input type="checkbox" v-model="selectedDomains[d.domain]" class="mr-2">
                    <span class="flex-1 truncate">{{ d.domain }}</span>
                    <select 
                      v-model="domainEngines[d.domain]" 
                      class="text-xs border rounded px-1 py-0.5 mr-2 bg-white"
                      @click.stop
                    >
                      <option v-for="e in engines" :key="e.value" :value="e.value">{{ e.label }}</option>
                    </select>
                    <span class="text-xs text-gray-400">{{ d.count }}</span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Download options -->
            <div class="mt-4 pt-4 border-t">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs text-gray-600 mb-1">Движок</label>
                  <select v-model="selectedEngine" class="input text-sm">
                    <option v-for="e in engines" :key="e.value" :value="e.value">{{ e.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs text-gray-600 mb-1">Глубина</label>
                  <input v-model.number="downloadDepth" type="number" min="1" max="10" class="input text-sm">
                </div>
              </div>
            </div>
          </div>
          
          <!-- Step 3: Downloading -->
          <div v-else-if="wizardStep === 3" class="p-5 flex-1 overflow-y-auto">
            <div class="bg-blue-50 rounded-lg p-6 text-center">
              <div class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <i class="fas fa-download text-2xl text-blue-600 animate-bounce"></i>
              </div>
              <h4 class="text-lg font-bold text-gray-900 mb-2">Скачивание запущено!</h4>
              <p class="text-sm text-gray-600">Прогресс отображается на странице</p>
            </div>
          </div>
          
          <!-- Footer -->
          <div class="p-4 border-t flex justify-between">
            <button 
              @click="closeWizard" 
              class="px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-gray-100 hover:bg-gray-200"
            >
              {{ wizardStep === 3 ? 'Закрыть' : 'Отмена' }}
            </button>
            <button 
              v-if="wizardStep === 2"
              @click="startSelectedDownload"
              :disabled="selectedDomainsCount === 0"
              class="px-6 py-2 text-sm font-medium rounded-lg text-white bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 disabled:opacity-50"
            >
              <i class="fas fa-download mr-2"></i>Скачать ({{ selectedDomainsCount }})
            </button>
          </div>
        </div>
      </div>
    </Teleport>
    
    <!-- Toast Notifications -->
    <Teleport to="body">
      <div class="fixed top-4 right-4 z-[9999] space-y-2 max-w-md">
        <TransitionGroup name="toast">
          <div
            v-for="toast in toasts"
            :key="toast.id"
            :class="[
              'px-4 py-3 rounded-lg shadow-lg flex items-start space-x-3 backdrop-blur-sm',
              toast.type === 'success' ? 'bg-green-500/90 text-white' : '',
              toast.type === 'error' ? 'bg-red-500/90 text-white' : '',
              toast.type === 'warning' ? 'bg-yellow-500/90 text-white' : '',
              toast.type === 'info' ? 'bg-blue-500/90 text-white' : ''
            ]"
          >
            <i :class="[
              'mt-0.5',
              toast.type === 'success' ? 'fas fa-check-circle' : '',
              toast.type === 'error' ? 'fas fa-exclamation-circle' : '',
              toast.type === 'warning' ? 'fas fa-exclamation-triangle' : '',
              toast.type === 'info' ? 'fas fa-info-circle' : ''
            ]"></i>
            <span class="text-sm flex-1">{{ toast.message }}</span>
            <button @click="toasts = toasts.filter(t => t.id !== toast.id)" class="text-white/70 hover:text-white">
              <i class="fas fa-times"></i>
            </button>
          </div>
        </TransitionGroup>
      </div>
    </Teleport>

    <!-- Confirm Modal -->
    <Teleport to="body">
      <div v-if="confirmModal.show" class="fixed inset-0 z-[60] flex items-center justify-center">
        <div class="absolute inset-0 bg-black/50" @click="confirmModal.show = false"></div>
        <div class="relative bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
          <h3 class="text-lg font-semibold text-gray-900 mb-2">{{ confirmModal.title }}</h3>
          <p class="text-gray-600 mb-6 whitespace-pre-wrap">{{ confirmModal.message }}</p>
          <div class="flex justify-end space-x-3">
            <button @click="confirmModal.show = false" class="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors">
              Отмена
            </button>
            <button @click="confirmModal.onConfirm(); confirmModal.show = false" class="px-4 py-2 text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors">
              {{ confirmModal.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLandingsStore } from '../stores/landings'
import { fetchApi, fetchJson } from '../utils/fetchApi'
import { config } from '../config'

const route = useRoute()
const router = useRouter()
const landingsStore = useLandingsStore()

const loading = ref(true)
const error = ref(null)
const siteData = ref({})
const landingMeta = ref(null)
const sortBy = ref('tag')
const filterTag = ref('')
const onlyRelevant = ref(false)
const activeTab = ref('subdomains')
const trackersData = ref(null)
const trackersLoading = ref(false)
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
const showEngineModal = ref(false)
const selectedEngine = ref('wget2')
const showLogsModal = ref(false)
const logsCopied = ref(false)
const autoScrollLogs = ref(true)
const logsContainer = ref(null)
const historyLogs = ref([])
const scriptsStatus = ref(null)
const generatingScripts = ref(false)
const showScriptsModal = ref(false)
const showOpenModal = ref(false)
const showNpmInstallModal = ref(false)
const showBackendModal = ref(false)
const startingServer = ref(null)  // 'vue' | 'backend' | null
const runningServers = ref({ vue: false, backend: false })
const restartingVue = ref(false)
const serverLaunchSteps = ref([])
const serverLaunchError = ref(null)

// Toast notifications system
const toasts = ref([])
let toastId = 0

function showToast(message, type = 'info', duration = 4000) {
  const id = ++toastId
  toasts.value.push({ id, message, type })
  if (duration > 0) {
    setTimeout(() => {
      toasts.value = toasts.value.filter(t => t.id !== id)
    }, duration)
  }
}

function showSuccess(message) { showToast(message, 'success') }
function showError(message) { showToast(message, 'error', 6000) }
function showInfo(message) { showToast(message, 'info') }
function showWarning(message) { showToast(message, 'warning', 5000) }

// Custom confirm modal
const confirmModal = reactive({
  show: false,
  title: '',
  message: '',
  confirmText: 'Подтвердить',
  onConfirm: () => {}
})

function showConfirm(title, message, onConfirm, confirmText = 'Подтвердить') {
  confirmModal.title = title
  confirmModal.message = message
  confirmModal.confirmText = confirmText
  confirmModal.onConfirm = onConfirm
  confirmModal.show = true
}

const scriptsOptions = ref({
  vueWrapper: true,
  backendServer: true,
  moveToSite: true,
  port: config.defaultServerPort
})

// Download wizard state
const showDownloadWizard = ref(false)
const wizardStep = ref(1) // 1: scanning, 2: select domains, 3: downloading
const scanId = ref(null)
const scanProgress = ref(0)
const scanPagesScanned = ref(0)
const scanCurrentUrl = ref('')
const scanResult = ref(null)
const scanStatus = ref('idle') // idle, running, completed
const selectedDomains = ref({})
const domainEngines = ref({}) // Движок для каждого домена: { 'domain.com': 'wget2' }
const downloadDepth = ref(config.defaultDownloadDepth)

const engines = [
  { value: 'wget2', label: 'wget2', icon: 'fas fa-bolt', color: '#3b82f6', desc: 'Быстрый, HTTP/2' },
  { value: 'puppeteer', label: 'Puppeteer', icon: 'fas fa-robot', color: '#8b5cf6', desc: 'JS-рендеринг' },
  { value: 'httrack', label: 'HTTrack', icon: 'fas fa-layer-group', color: '#f59e0b', desc: 'Классический' },
  { value: 'smart', label: 'Smart', icon: 'fas fa-brain', color: '#10b981', desc: 'Все движки' }
]

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

const currentLogs = computed(() => {
  // Если есть активная задача - показываем её логи, иначе историю
  if (activeJob.value?.logs?.length) {
    return activeJob.value.logs
  }
  return historyLogs.value
})

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

async function loadTrackers() {
  trackersLoading.value = true
  try {
    const data = await fetchJson(`/api/downloads/${folderName.value}/trackers`)
    trackersData.value = data
  } catch (err) {
    console.error('Error loading trackers:', err)
    showError('Ошибка сканирования трекеров: ' + err.message)
  } finally {
    trackersLoading.value = false
  }
}

function trackerTypeColor(type) {
  const colors = {
    'Google Tag Manager': 'bg-blue-100 text-blue-700',
    'GTM noscript': 'bg-blue-100 text-blue-700',
    'Google Analytics': 'bg-orange-100 text-orange-700',
    'Google Site Verification': 'bg-gray-100 text-gray-700',
    'Facebook Pixel': 'bg-indigo-100 text-indigo-700',
    'Facebook Pixel noscript': 'bg-indigo-100 text-indigo-700',
    'TradeDesk': 'bg-purple-100 text-purple-700',
    'BubbleUp mydata': 'bg-pink-100 text-pink-700',
    'Shopify web-pixels-manager': 'bg-green-100 text-green-700',
    'Shopify Trekkie': 'bg-green-100 text-green-700',
    'Cookiebot': 'bg-yellow-100 text-yellow-700',
    'Hotjar': 'bg-red-100 text-red-700',
    'Preconnect monorail': 'bg-gray-100 text-gray-600',
    'DNS prefetch shop.app': 'bg-gray-100 text-gray-600',
  }
  return colors[type] || 'bg-yellow-100 text-yellow-700'
}

async function loadFileTree() {
  fileTreeLoading.value = true
  try {
    const data = await fetchJson(`/api/file-tree/${folderName.value}`)
    
    // API returns hierarchical tree with children - flatten to file list
    const flatFiles = []
    function flattenTree(nodes) {
      for (const node of nodes) {
        if (node.type === 'directory' && node.children) {
          flattenTree(node.children)
        } else if (node.type === 'file') {
          const ext = node.name.includes('.') ? node.name.split('.').pop().toLowerCase() : ''
          const typeMap = { html: 'html', htm: 'html', css: 'css', js: 'js', png: 'image', jpg: 'image', jpeg: 'image', gif: 'image', svg: 'image', webp: 'image', ico: 'image' }
          flatFiles.push({
            name: node.name,
            path: node.path,
            size: node.size || 0,
            size_bytes: node.size || 0,
            type: typeMap[ext] || 'other',
            ext: ext
          })
        }
      }
    }
    
    const treeNodes = Array.isArray(data) ? data : (data.files || data.children || [])
    flattenTree(treeNodes)
    
    fileTreeData.value = { files: flatFiles }
    
    // Auto-expand first level
    if (flatFiles.length) {
      const firstLevel = {}
      for (const f of flatFiles) {
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
    showError('Не удалось определить URL оригинала')
    return
  }
  showConfirm('Перескачать файл?', `Перескачать "${file.name}"?\n\nURL: ${originalUrl}`, async () => {
    try {
      const data = await fetchJson('/api/landings/redownload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: originalUrl,
          folder_name: folderName.value,
          config_key: ''
        })
      })
      if (data.id) {
        showSuccess(`Перескачивание запущено! Job ID: ${data.id}`)
      } else {
        showError(data.error || 'Неизвестная ошибка')
      }
    } catch (err) {
      showError(err.message)
    }
  })
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
    const data = await fetchJson(`/api/check-all-changes/${folderName.value}?max=100`)
    changesData.value = data
  } catch (err) {
    showError('Ошибка проверки: ' + err.message)
  } finally {
    changesLoading.value = false
  }
}

function updateAllChanged() {
  if (!changesData.value) return
  const changedPages = changesData.value.pages.filter(p => p.has_changes)
  if (changedPages.length === 0) return
  
  showConfirm('Обновить страницы?', `Обновить ${changedPages.length} изменённых страниц?`, async () => {
    updatingPages.value = true
    const paths = changedPages.map(p => p.page)
    
    try {
      const data = await fetchJson(`/api/download-missing/${folderName.value}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths })
      })
      showSuccess(`Обновлено: ${data.downloaded} / ${data.total}${data.failed > 0 ? ', ошибок: ' + data.failed : ''}`)
      await checkAllChanges()
    } catch (err) {
      showError(err.message)
    } finally {
      updatingPages.value = false
    }
  }, 'Обновить')
}

async function updateSinglePage(page) {
  try {
    const data = await fetchJson(`/api/download-missing/${folderName.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: [page.page] })
    })
    if (data.downloaded > 0) {
      // Update status in local data
      page.status = 'unchanged'
      page.has_changes = false
      changesData.value.changed--
      changesData.value.unchanged++
    } else {
      showError('Не удалось обновить: ' + (data.errors?.[0] || 'Неизвестная ошибка'))
    }
  } catch (err) {
    showError(err.message)
  }
}

async function generateThumbnail() {
  generatingThumb.value = true
  try {
    const data = await fetchJson(`/api/screenshot/${folderName.value}`, { method: 'POST' })
    if (data.path) {
      thumbnailUrl.value = `/api/thumbnail/${folderName.value}?t=${Date.now()}`
      thumbnailError.value = false
    } else {
      showError('Не удалось создать скриншот: ' + (data.error || 'Неизвестная ошибка'))
    }
  } catch (err) {
    showError(err.message)
  } finally {
    generatingThumb.value = false
  }
}

function redownloadSite() {
  // Устанавливаем текущий движок сайта как выбранный по умолчанию
  selectedEngine.value = siteData.value.engine || 'wget2'
  showEngineModal.value = true
}

async function confirmRedownload() {
  showEngineModal.value = false
  
  try {
    const data = await fetchJson(`/api/downloads/${folderName.value}/restart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        engine: selectedEngine.value
      })
    })
    if (data.id) {
      activeJob.value = { id: data.id, progress: 0 }
      pollJobProgress(data.id)
    } else {
      showError(data.error || 'Неизвестная ошибка')
    }
  } catch (err) {
    showError(err.message)
  }
}

let pollInterval = null

function pollJobProgress(jobId) {
  if (pollInterval) clearInterval(pollInterval)
  
  pollInterval = setInterval(async () => {
    try {
      const data = await fetchJson(`/api/jobs/${jobId}`)
      
      activeJob.value = {
        id: jobId,
        progress: data.progress || 0,
        files: data.files_downloaded || 0,
        size: data.total_size || '0 B',
        lastLog: data.output_lines?.slice(-1)[0] || 'Скачивание...',
        logs: data.output_lines || [],
        status: data.status
      }
      
      // Автопрокрутка логов
      if (autoScrollLogs.value && logsContainer.value) {
        logsContainer.value.scrollTop = logsContainer.value.scrollHeight
      }
      
      if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
        clearInterval(pollInterval)
        pollInterval = null
        
        // Show completion message
        if (data.status === 'completed') {
          showSuccess(`Скачивание завершено! Файлов: ${data.files_downloaded || 0}`)
        } else if (data.status === 'failed') {
          showError('Скачивание не удалось')
        }
        
        // Reload site data but keep activeJob visible until user closes
        loadSiteData(false)
      }
    } catch (err) {
      console.error('Poll error:', err)
    }
  }, 1000)
}

function copyJobLogs() {
  if (!activeJob.value?.logs?.length) {
    showWarning('Нет логов для копирования')
    return
  }
  const text = activeJob.value.logs.join('\n')
  navigator.clipboard.writeText(text).then(() => {
    logsCopied.value = true
    showSuccess('Логи скопированы в буфер обмена')
    setTimeout(() => { logsCopied.value = false }, 2000)
  })
}

function copyLogs() {
  const logs = activeJob.value?.logs?.length ? activeJob.value.logs : historyLogs.value
  if (!logs.length) return
  const text = logs.join('\n')
  navigator.clipboard.writeText(text).then(() => {
    logsCopied.value = true
    setTimeout(() => { logsCopied.value = false }, 2000)
  })
}

function getLogLineClass(line) {
  if (!line) return 'text-green-400'
  if (line.includes('Error') || line.includes('error') || line.includes('❌')) return 'text-red-400'
  if (line.includes('Warning') || line.includes('warning') || line.includes('⚠️')) return 'text-yellow-400'
  if (line.includes('✅') || line.includes('completed') || line.includes('Done')) return 'text-green-400'
  if (line.includes('Downloading') || line.includes('Скачивание')) return 'text-blue-400'
  if (line.startsWith('[')) return 'text-cyan-400'
  return 'text-gray-300'
}

async function showHistoryLogs() {
  // Загружаем логи последней задачи для этого сайта
  try {
    const jobs = await fetchJson('/api/jobs')
    
    // Ищем последнюю задачу для этого сайта
    const siteJobs = jobs.filter(j => 
      j.folder_name === folderName.value || 
      j.url?.includes(siteData.value.domain)
    ).sort((a, b) => new Date(b.started_at || 0) - new Date(a.started_at || 0))
    
    if (siteJobs.length > 0 && siteJobs[0].output_lines) {
      historyLogs.value = siteJobs[0].output_lines
    } else {
      historyLogs.value = ['Логи не найдены для этого сайта']
    }
    showLogsModal.value = true
  } catch (err) {
    historyLogs.value = ['Ошибка загрузки логов: ' + err.message]
    showLogsModal.value = true
  }
}

function stopRedownload() {
  if (!activeJob.value?.id) return
  showConfirm('Остановить?', 'Остановить перекачивание?', async () => {
    try {
      await fetchApi(`/api/jobs/${activeJob.value.id}/stop`, { method: 'POST' })
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
      activeJob.value = null
    } catch (err) {
      showError(err.message)
    }
  }, 'Остановить')
}

function loadThumbnail() {
  // Reset error state and load thumbnail
  thumbnailError.value = false
  thumbnailUrl.value = `/api/thumbnail/${folderName.value}?t=${Date.now()}`
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
    showWarning(`Папка "${folderNode.name}" не содержит HTML файлов`)
    return
  }
  
  showInfo(`Проверяю ${htmlFiles.length} HTML файлов...`)
  
  let changed = 0
  let errors = 0
  let upToDate = 0
  
  for (const file of htmlFiles) {
    try {
      const result = await fetchJson(`/api/check-changes/${folderName.value}?page=${encodeURIComponent(file.path)}`)
      if (result.error) errors++
      else if (result.has_changes) changed++
      else upToDate++
    } catch (err) {
      errors++
    }
  }
  
  showInfo(`Проверка: ${htmlFiles.length} файлов, изменено: ${changed}, актуально: ${upToDate}`)
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
    showWarning(`Папка "${folderNode.name}" не содержит HTML файлов`)
    return
  }
  
  showConfirm('Перескачать папку?', `Перескачать ${htmlFiles.length} HTML файлов из "${folderNode.name}"?`, async () => {
    const paths = htmlFiles.map(f => f.path)
    try {
      const data = await fetchJson(`/api/download-missing/${folderName.value}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths })
      })
      showSuccess(`Перескачано: ${data.downloaded} / ${data.total}${data.failed > 0 ? ', ошибок: ' + data.failed : ''}`)
      if (data.downloaded > 0) loadFileTree()
    } catch (err) {
      showError(err.message)
    }
  }, 'Перескачать')
}

async function checkIntegrity() {
  integrityLoading.value = true
  integrityResult.value = null
  downloadResult.value = null
  try {
    const data = await fetchJson(`/api/check-integrity/${folderName.value}`)
    integrityResult.value = data
  } catch (err) {
    showError('Ошибка проверки целостности: ' + err.message)
  } finally {
    integrityLoading.value = false
  }
}

function downloadAllMissing() {
  if (!integrityResult.value || !integrityResult.value.missing) return
  const paths = integrityResult.value.missing.map(m => m.path)
  
  showConfirm('Докачать файлы?', `Докачать ${paths.length} файлов?`, async () => {
    downloadingMissing.value = true
    downloadResult.value = null
    try {
      const data = await fetchJson(`/api/download-missing/${folderName.value}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths })
      })
      downloadResult.value = data
      if (data.downloaded > 0) {
        loadFileTree()
      }
    } catch (err) {
      showError('Ошибка докачки: ' + err.message)
    } finally {
      downloadingMissing.value = false
    }
  }, 'Докачать')
}

async function downloadSingleMissing(path) {
  try {
    const data = await fetchJson(`/api/download-missing/${folderName.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: [path] })
    })
    if (data.downloaded > 0) {
      showSuccess(`Скачан: ${path}`)
      // Remove from missing list
      if (integrityResult.value && integrityResult.value.missing) {
        integrityResult.value.missing = integrityResult.value.missing.filter(m => m.path !== path)
        integrityResult.value.total_missing = integrityResult.value.missing.length
        integrityResult.value.is_complete = integrityResult.value.missing.length === 0
      }
    } else {
      showError(`Не удалось скачать: ${path}`)
    }
  } catch (err) {
    showError(err.message)
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

async function loadSiteData(showLoading = true) {
  if (showLoading) {
    loading.value = true
  }
  error.value = null
  
  try {
    await landingsStore.loadLandings()
    
    // Найти сайт в списке лендингов
    for (const domain of landingsStore.landings) {
      const folder = domain.folders.find(f => f.folder_name === folderName.value)
      if (folder) {
        siteData.value = folder
        landingMeta.value = folder.landing_meta || null
        loading.value = false
        // Загрузить статус скриптов
        loadScriptsStatus()
        loadServersStatus()
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

function closeWizard() {
  showDownloadWizard.value = false
  // Clear activeJob only if completed/failed
  if (activeJob.value && (activeJob.value.status === 'completed' || activeJob.value.status === 'failed')) {
    activeJob.value = null
  }
}

function continueDownloadWizard() {
  // Открываем wizard прямо здесь
  showDownloadWizard.value = true
  
  // Если уже есть результат сканирования - показываем выбор доменов
  if (landingMeta.value?.scan_result) {
    scanResult.value = landingMeta.value.scan_result
    scanStatus.value = 'completed'
    wizardStep.value = 2
    
    // Pre-select main domains and set default engine
    initDomainEngines(scanResult.value)
    if (scanResult.value.categories?.main) {
      scanResult.value.categories.main.forEach(d => {
        if (d.is_main) {
          selectedDomains.value[d.domain] = true
        }
      })
    }
  } else {
    // Запускаем сканирование
    wizardStep.value = 1
    startScan()
  }
}

async function startScan() {
  scanStatus.value = 'running'
  scanProgress.value = 0
  scanPagesScanned.value = 0
  
  try {
    const data = await fetchJson('/api/scan-async', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: landingMeta.value?.url || `https://${siteData.value.domain}`,
        folder_name: folderName.value,
        max_pages: config.defaultScanMaxPages
      })
    })
    scanId.value = data.scan_id
    pollScanProgress()
  } catch (err) {
    showError(err.message)
  }
}

async function pollScanProgress() {
  if (!scanId.value) return
  if (scanStatus.value === 'completed' && wizardStep.value === 2) return
  
  try {
    const data = await fetchJson(`/api/scan-status/${scanId.value}`)
    
    scanProgress.value = data.progress || 0
    scanPagesScanned.value = data.pages_scanned || 0
    
    if (data.status === 'completed' && data.result) {
      scanStatus.value = 'completed'
      scanResult.value = data.result
      wizardStep.value = 2
      
      // Init domain engines and pre-select main domains
      initDomainEngines(data.result)
      if (data.result.categories?.main) {
        data.result.categories.main.forEach(d => {
          if (d.is_main) {
            selectedDomains.value[d.domain] = true
          }
        })
      }
      
      // Reload landing meta in background without showing loading spinner
      loadSiteData(false)
    } else if (data.status === 'running') {
      setTimeout(pollScanProgress, 1000)
    } else {
      // Unknown status, keep polling
      setTimeout(pollScanProgress, 1000)
    }
  } catch (err) {
    console.error('Poll error:', err)
    setTimeout(pollScanProgress, 2000)
  }
}

function getSelectedDomainsList() {
  return Object.entries(selectedDomains.value)
    .filter(([_, v]) => v)
    .map(([k, _]) => k)
}

// Инициализация движков для всех доменов (по умолчанию selectedEngine)
function initDomainEngines(result) {
  if (!result?.categories) return
  const defaultEngine = selectedEngine.value || 'wget2'
  
  // Main domains
  if (result.categories.main) {
    result.categories.main.forEach(d => {
      if (!domainEngines.value[d.domain]) {
        domainEngines.value[d.domain] = defaultEngine
      }
    })
  }
  // CDN domains
  if (result.categories.cdn) {
    result.categories.cdn.forEach(d => {
      if (!domainEngines.value[d.domain]) {
        domainEngines.value[d.domain] = defaultEngine
      }
    })
  }
  // Related domains
  if (result.categories.related) {
    result.categories.related.forEach(d => {
      if (!domainEngines.value[d.domain]) {
        domainEngines.value[d.domain] = defaultEngine
      }
    })
  }
}

// Получить список выбранных доменов с их движками
function getSelectedDomainsWithEngines() {
  return Object.entries(selectedDomains.value)
    .filter(([_, v]) => v)
    .map(([domain, _]) => ({
      domain,
      engine: domainEngines.value[domain] || selectedEngine.value || 'wget2'
    }))
}

const selectedDomainsCount = computed(() => {
  return Object.values(selectedDomains.value).filter(v => v).length
})

function selectAllDomains(category) {
  if (!scanResult.value?.categories?.[category]) return
  scanResult.value.categories[category].forEach(d => {
    selectedDomains.value[d.domain] = true
  })
}

function deselectAllDomains() {
  Object.keys(selectedDomains.value).forEach(k => {
    selectedDomains.value[k] = false
  })
}

function allDomainsSelected(category) {
  if (!scanResult.value?.categories?.[category]) return false
  return scanResult.value.categories[category].every(d => selectedDomains.value[d.domain])
}

function toggleDomainCategory(category) {
  const all = allDomainsSelected(category)
  scanResult.value.categories[category].forEach(d => {
    selectedDomains.value[d.domain] = !all
  })
}

async function startSelectedDownload() {
  const selected = getSelectedDomainsList()
  const domainsWithEngines = getSelectedDomainsWithEngines()
  
  if (selected.length === 0) {
    showWarning('Выберите хотя бы один домен')
    return
  }
  
  wizardStep.value = 3
  
  try {
    const data = await fetchJson('/api/start-download-selected', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_name: folderName.value,
        url: landingMeta.value?.url || `https://${siteData.value.domain}`,
        selected_domains: selected,
        domains_with_engines: domainsWithEngines, // Домены с индивидуальными движками
        engine: selectedEngine.value, // Движок по умолчанию
        options: {
          depth: downloadDepth.value
        }
      })
    })
    if (data.id || data.job_id) {
      const jobId = data.id || data.job_id
      activeJob.value = { id: jobId, progress: 0, status: 'running' }
      
      // Close wizard and show progress bar at top of page
      showDownloadWizard.value = false
      
      // Start polling for progress
      pollJobProgress(jobId)
    } else {
      showError(data.error || data.detail?.error || 'Неизвестная ошибка')
      wizardStep.value = 2
    }
  } catch (err) {
    showError(err.message)
    wizardStep.value = 2
  }
}

async function loadScriptsStatus() {
  try {
    scriptsStatus.value = await fetchJson(`/api/downloads/${folderName.value}/scripts-status`)
  } catch (err) {
    console.error('Ошибка загрузки статуса скриптов:', err)
  }
}

function generateScripts() {
  // Открываем попап выбора опций
  showScriptsModal.value = true
}

async function confirmGenerateScripts() {
  showScriptsModal.value = false
  generatingScripts.value = true
  
  try {
    const data = await fetchJson(`/api/downloads/${folderName.value}/generate-scripts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        port: scriptsOptions.value.port,
        vue_wrapper: scriptsOptions.value.vueWrapper,
        backend_server: scriptsOptions.value.backendServer,
        move_to_site: scriptsOptions.value.moveToSite
      })
    })
    
    if (data.success) {
      showSuccess('Скрипты созданы!')
      loadScriptsStatus()
    } else {
      showError(data.error || 'Неизвестная ошибка')
    }
  } catch (err) {
    showError('Ошибка генерации: ' + err.message)
  } finally {
    generatingScripts.value = false
  }
}

function openInBrowser() {
  // Открываем попап выбора платформы
  serverLaunchSteps.value = []
  serverLaunchError.value = null
  showOpenModal.value = true
}

async function openStaticHtml() {
  showOpenModal.value = false
  try {
    const data = await fetchJson(`/api/find-index/${folderName.value}`)
    
    if (data.index_path) {
      window.open(`/api/browse/${folderName.value}/${data.index_path}`, '_blank')
    } else {
      showWarning('Не найден index.html файл')
    }
  } catch (err) {
    showError('Ошибка открытия сайта: ' + err.message)
  }
}

function stepLabel(name) {
  const labels = {
    'scripts_status': 'Статус',
    'vue-app': 'Vue App',
    'package.json': 'package.json',
    'backend-server.js': 'Backend JS',
    'ports': 'Порты',
    'servers_check': 'Серверы',
    'backend_check': 'Backend',
    'stop_servers': 'Остановка',
    'already_running': 'Уже запущен',
    'sync_templates': 'Шаблоны',
    'npm_install': 'npm install',
    'port_cleanup': 'Порт Backend',
    'port_cleanup_vue': 'Порт Vue',
    'backend_start': 'Backend',
    'vue_start': 'Vue Vite',
    'verify': 'Проверка',
  }
  return labels[name] || name
}

function copyLaunchLogs() {
  const statusIcons = { ok: '[OK]', error: '[ERR]', warn: '[WARN]', running: '[...]', skip: '[SKIP]' }
  const lines = serverLaunchSteps.value.map(s => {
    const icon = statusIcons[s.status] || '[?]'
    return `${icon} ${stepLabel(s.name)}${s.detail ? ' - ' + s.detail : ''}`
  })
  if (serverLaunchError.value) {
    lines.push(`\n[ERROR] ${serverLaunchError.value}`)
  }
  const text = `WCLoner Launch Log\n${'='.repeat(40)}\n${lines.join('\n')}`
  navigator.clipboard.writeText(text).then(() => {
    showToast('Логи скопированы', 'success', 2000)
  }).catch(() => {
    showToast('Не удалось скопировать', 'error', 2000)
  })
}

function addStep(name, status, detail = '') {
  serverLaunchSteps.value = [...serverLaunchSteps.value, { name, status, detail }]
}

function updateLastStep(status, detail) {
  const steps = [...serverLaunchSteps.value]
  if (steps.length > 0) {
    steps[steps.length - 1] = { ...steps[steps.length - 1], status, detail }
    serverLaunchSteps.value = steps
  }
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function openVueWrapper() {
  // Показываем прогресс запуска/проверки
  startingServer.value = 'vue'
  serverLaunchSteps.value = []
  serverLaunchError.value = null
  
  // --- Шаг 1: Загрузка статуса скриптов ---
  addStep('scripts_status', 'running', 'Загрузка статуса...')
  await wait(200)
  try {
    scriptsStatus.value = await fetchJson(`/api/downloads/${folderName.value}/scripts-status`)
    updateLastStep('ok', 'Статус получен')
  } catch (e) {
    updateLastStep('error', 'Не удалось получить статус: ' + e.message)
    serverLaunchError.value = 'Не удалось получить статус скриптов'
    startingServer.value = null
    return
  }
  await wait(150)
  
  // --- Шаг 2: Проверка vue-app ---
  addStep('vue-app', 'running', 'Проверка vue-app...')
  await wait(200)
  const hasVue = scriptsStatus.value?.vue_wrapper?.ready
  if (!hasVue) {
    updateLastStep('error', 'Vue обертка не найдена')
    serverLaunchError.value = 'Сначала сгенерируйте скрипты'
    startingServer.value = null
    return
  }
  updateLastStep('ok', 'Vue обертка готова')
  await wait(150)
  
  // --- Шаг 3: Проверка backend-server.js ---
  addStep('backend-server.js', 'running', 'Проверка backend-server.js...')
  await wait(200)
  const hasBackend = scriptsStatus.value?.backend_server?.ready
  updateLastStep(hasBackend ? 'ok' : 'warn', hasBackend ? 'Файл найден' : 'Не найден, будет создан')
  await wait(150)
  
  // --- Шаг 4: Проверка серверов ---
  addStep('servers_check', 'running', 'Проверка запущенных серверов...')
  await wait(200)
  try {
    const srvStatus = await fetchJson(`/api/downloads/${folderName.value}/servers-status`)
    const vueRunning = srvStatus?.vue_server?.running
    const backendRunning = srvStatus?.backend_server?.running
    if (vueRunning) {
      updateLastStep('ok', `Vue уже запущен на :${srvStatus.vue_server.port}`)
      runningServers.value.vue = { port: srvStatus.vue_server.port, pid: srvStatus.vue_server.pid, url: srvStatus.vue_server.url || `http://localhost:${srvStatus.vue_server.port}` }
      if (backendRunning) {
        addStep('backend_check', 'ok', `Backend на :${srvStatus.backend_server.port}`)
        runningServers.value.backend = { port: srvStatus.backend_server.port, pid: srvStatus.backend_server.pid }
      }
      addStep('verify', 'ok', `http://localhost:${srvStatus.vue_server.port} - серверы работают`)
      // Серверы уже работают - не запускаем повторно, покажем кнопки
      startingServer.value = null
      return
    } else {
      updateLastStep('ok', 'Серверы не запущены, будут запущены')
    }
  } catch (e) {
    updateLastStep('warn', 'Не удалось проверить: ' + e.message)
  }
  await wait(150)
  
  // --- Шаги 5-8: Предварительные плейсхолдеры ---
  addStep('sync_templates', 'running', 'Синхронизация шаблонов...')
  addStep('npm_install', 'running', 'Проверка зависимостей...')
  addStep('backend_start', 'running', 'Запуск Backend сервера...')
  addStep('vue_start', 'running', 'Запуск Vue Vite...')
  addStep('verify', 'running', 'Ожидание...')
  
  // --- Вызов API ---
  try {
    const data = await fetchJson(`/api/downloads/${folderName.value}/start-vue`, { method: 'POST' })
    
    // Заменяем предварительные шаги реальными от сервера
    if (data.steps && data.steps.length > 0) {
      serverLaunchSteps.value = data.steps
    }
    
    if (data.status === 'started' || data.status === 'already_running') {
      runningServers.value.vue = { port: data.vue_port, pid: data.vue_pid, url: data.url }
      if (data.backend_port) {
        runningServers.value.backend = { port: data.backend_port, pid: data.backend_pid }
      }
      // Не открываем автоматически - пользователь нажмёт "Открыть сайт"
    } else {
      serverLaunchError.value = data.error || 'Неизвестная ошибка'
    }
  } catch (err) {
    serverLaunchError.value = err.message
  } finally {
    startingServer.value = null
  }
}

function openVueSite() {
  const url = runningServers.value.vue?.url || `http://localhost:${runningServers.value.vue?.port}`
  showOpenModal.value = false
  window.open(url, '_blank')
}

async function restartAndRecheck() {
  startingServer.value = 'restarting'
  serverLaunchSteps.value = []
  serverLaunchError.value = null
  
  addStep('stop_servers', 'running', 'Остановка серверов...')
  try {
    await fetchApi(`/api/downloads/${folderName.value}/stop-vue`, { method: 'POST' })
    await fetchApi(`/api/downloads/${folderName.value}/stop-servers`, { method: 'POST' })
    updateLastStep('ok', 'Серверы остановлены')
  } catch (e) {
    updateLastStep('warn', 'Ошибка остановки: ' + e.message)
  }
  await wait(500)
  
  // Сбрасываем runningServers
  runningServers.value.vue = null
  runningServers.value.backend = null
  startingServer.value = null
  
  // Запускаем полный цикл проверки и запуска
  await openVueWrapper()
}

async function restartVueServer() {
  restartingVue.value = true
  
  try {
    // Останавливаем текущий сервер
    await fetchApi(`/api/downloads/${folderName.value}/stop-vue`, { method: 'POST' })
    
    // Небольшая пауза
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // Запускаем заново
    const data = await fetchJson(`/api/downloads/${folderName.value}/start-vue`, { method: 'POST' })
    
    if (data.status === 'started' || data.status === 'already_running') {
      runningServers.value.vue = { port: data.vue_port, pid: data.vue_pid, url: data.url }
      showToast('Vue сервер перезапущен', 'success')
    } else {
      showError('Ошибка перезапуска: ' + (data.error || 'Неизвестная ошибка'))
    }
  } catch (err) {
    showError(err.message)
  } finally {
    restartingVue.value = false
  }
}

async function openBackendServer() {
  // НЕ закрываем попап - показываем прогресс
  startingServer.value = 'backend'
  
  try {
    const data = await fetchJson(`/api/downloads/${folderName.value}/start-backend`, { method: 'POST' })
    
    if (data.status === 'started' || data.status === 'already_running') {
      runningServers.value.backend = { port: data.port, pid: data.pid, url: data.url }
      showOpenModal.value = false
      window.open(data.url, '_blank')
    } else {
      showError('Ошибка запуска Backend: ' + (data.error || 'Неизвестная ошибка'))
    }
  } catch (err) {
    showError(err.message)
  } finally {
    startingServer.value = null
  }
}

async function loadServersStatus() {
  try {
    const data = await fetchJson(`/api/downloads/${folderName.value}/servers-status`)
    runningServers.value = {
      vue: data.vue_server?.running ? data.vue_server : false,
      backend: data.backend_server?.running ? data.backend_server : false
    }
  } catch (err) {
    console.error('Error loading servers status:', err)
  }
}

async function stopAllServers() {
  try {
    await fetchApi(`/api/downloads/${folderName.value}/stop-servers`, { method: 'POST' })
    runningServers.value = { vue: false, backend: false }
  } catch (err) {
    console.error('Error stopping servers:', err)
  }
}

function openFolder() {
  fetchApi(`/api/open-folder?path=${encodeURIComponent(siteData.value.path)}`)
    .catch(err => showError('Ошибка открытия папки: ' + err.message))
}

function openSubdomain(subdomain) {
  const indexPage = subdomain.pages.find(p => p.name === 'index.html')
  if (indexPage) {
    window.open(`/api/browse/${folderName.value}/${indexPage.path}`, '_blank')
  }
}

function openSubdomainFolder(subdomain) {
  const subPath = siteData.value.path + '/' + subdomain.name
  fetchApi(`/api/open-folder?path=${encodeURIComponent(subPath)}`)
    .catch(err => showError('Ошибка открытия папки поддомена: ' + err.message))
}

async function downloadSubdomain(subdomain) {
  const url = `https://${subdomain.name}`
  try {
    const data = await fetchJson('/api/landings/redownload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        folder_name: folderName.value,
        config_key: subdomain.config_key
      })
    })
    if (data.id) {
      showSuccess(`Скачивание запущено! URL: ${url}`)
    } else {
      showError(data.error || 'Неизвестная ошибка')
    }
  } catch (err) {
    showError('Ошибка запуска скачивания: ' + err.message)
  }
}

function redownloadSubdomain(subdomain) {
  showConfirm('Перескачать поддомен?', `Перескачать поддомен "${subdomain.name}"?\n\nЭто обновит все файлы.`, async () => {
    const url = `https://${subdomain.name}`
    try {
      const data = await fetchJson('/api/landings/redownload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: url,
          folder_name: folderName.value,
          config_key: subdomain.config_key
        })
      })
      if (data.id) {
        showSuccess(`Перескачивание запущено! URL: ${url}`)
      } else {
        showError(data.error || 'Неизвестная ошибка')
      }
    } catch (err) {
      showError('Ошибка запуска перескачивания: ' + err.message)
    }
  }, 'Перескачать')
}

async function checkPageChanges(page) {
  const origUrl = page.originalUrl || getOriginalUrl(page.path)
  if (!origUrl) {
    showError('Не удалось определить URL оригинала')
    return
  }
  
  try {
    const result = await fetchJson(`/api/check-changes/${folderName.value}?page=${encodeURIComponent(page.path)}`)
    
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
    
    showInfo(result.has_changes ? 'Обнаружены изменения на сайте' : 'Изменений не обнаружено')
  } catch (err) {
    showError('Ошибка проверки: ' + err.message)
  }
}

async function checkSubdomainChanges(subdomain) {
  try {
    const result = await fetchJson(`/api/check-changes/${folderName.value}?subdomain=${encodeURIComponent(subdomain.name)}`)
    
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
    
    showInfo(result.has_changes ? 'Обнаружены изменения на сайте' : 'Изменений не обнаружено')
  } catch (err) {
    showError('Ошибка проверки: ' + err.message)
  }
}

async function setSubdomainTag(subdomain, tagId) {
  try {
    const newConfig = { ...subdomain.config, tag: tagId }
    await fetchApi('/api/landings/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        config_key: subdomain.config_key,
        settings: newConfig
      })
    })
    
    const sub = siteData.value.subdomains.find(s => s.name === subdomain.name)
    if (sub) {
      if (!sub.config) sub.config = {}
      sub.config.tag = tagId
    }
  } catch (err) {
    console.error('Ошибка сохранения тега:', err)
  }
}

async function toggleSubdomainExclude(subdomain) {
  const newExcluded = !subdomain.excluded
  
  try {
    await fetchApi('/api/landings/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        config_key: subdomain.config_key,
        settings: { ...subdomain.config, excluded: newExcluded }
      })
    })
    
    // Обновляем данные в siteData напрямую
    const sub = siteData.value.subdomains.find(s => s.name === subdomain.name)
    if (sub) {
      if (!sub.config) sub.config = {}
      sub.config.excluded = newExcluded
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
    
    showInfo(result.has_changes ? 'Обнаружены изменения на сайте' : 'Изменений не обнаружено')
  } catch (err) {
    showError('Ошибка проверки: ' + err.message)
  }
}

function deleteSite() {
  showConfirm('Удалить сайт?', `Удалить "${siteData.value.domain}"?\n\nЭто действие нельзя отменить!`, async () => {
    try {
      await landingsStore.deleteFolder(folderName.value)
      router.push('/landings')
    } catch (err) {
      showError('Ошибка удаления: ' + err.message)
    }
  }, 'Удалить')
}

async function checkActiveJobs() {
  try {
    const jobs = await fetchJson('/api/jobs')
    
    // Find jobs for this folder, sorted by date descending (newest first)
    const folderJobs = jobs
      .filter(j => j.output_dir?.includes(folderName.value))
      .sort((a, b) => new Date(b.started_at || 0) - new Date(a.started_at || 0))
    
    if (!folderJobs.length) return
    
    // Show progress block ONLY for currently running jobs
    const runningJob = folderJobs.find(j => j.status === 'running')
    
    if (runningJob) {
      activeJob.value = {
        id: runningJob.id,
        progress: runningJob.progress || 0,
        files: runningJob.files_downloaded || 0,
        size: runningJob.total_size || '0 B',
        status: runningJob.status,
        logs: runningJob.output_lines || []
      }
      pollJobProgress(runningJob.id)
    }
  } catch (err) {
    console.error('Error checking active jobs:', err)
  }
}

onMounted(async () => {
  loadFolderTags()
  loadThumbnail()
  await loadSiteData()
  loadFileTree()
  
  // Check for active download jobs
  await checkActiveJobs()
  
  // No automatic actions - user must manually click buttons to start any downloads/scans
  // Clear any wizard parameter from URL
  if (route.query.wizard) {
    router.replace({ path: route.path, query: {} })
  }
})
</script>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease-out;
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
