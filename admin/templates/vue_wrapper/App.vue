<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps({
  landing: Object,
  editorMode: Boolean
})

const route = useRoute()

// Читаем page из route.query ИЛИ из window.location (fallback при refresh)
function getInitialPage() {
  if (route.query.page) return route.query.page
  try {
    const params = new URLSearchParams(window.location.search)
    return params.get('page') || ''
  } catch (e) {
    return ''
  }
}

const page = ref(getInitialPage())
const iframeSrc = ref(resolveIframeSrc(page.value))
const iframeRef = ref(null)
const initialLoad = ref(true)

// SEO данные
const seoTitle = ref('')
const seoDescription = ref('')
const seoH1 = ref('')
const seoH2s = ref([])
const seoTexts = ref([])

function resolveIframeSrc(p) {
  if (!p) return '/__raw/'
  return '/__raw/' + p
}

// Обновление iframe при изменении route
function updateIframe() {
  const newPage = route.query.page || ''
  if (newPage !== page.value) {
    page.value = newPage
    iframeSrc.value = resolveIframeSrc(newPage)
  }
}

// Следим за изменением query параметра page
watch(() => route.query.page, (newPage) => {
  updateIframe()
})

// Извлечение SEO данных из iframe
function extractSEO() {
  try {
    const iframe = iframeRef.value
    if (!iframe || !iframe.contentDocument) return
    
    const doc = iframe.contentDocument
    
    // Title
    const title = doc.title || ''
    if (title) {
      seoTitle.value = title
      document.title = title
    }
    
    // Meta description
    const metaDesc = doc.querySelector('meta[name="description"]')
    if (metaDesc) {
      seoDescription.value = metaDesc.getAttribute('content') || ''
      setMetaTag('description', seoDescription.value)
      setMetaTag('og:description', seoDescription.value, 'property')
    }
    
    // OG image
    const ogImg = doc.querySelector('meta[property="og:image"]')
    if (ogImg) {
      const imgUrl = ogImg.getAttribute('content') || ''
      setMetaTag('og:image', imgUrl, 'property')
    }
    
    // Headings
    const h1 = doc.querySelector('h1')
    if (h1) seoH1.value = h1.textContent?.trim() || ''
    
    const h2s = doc.querySelectorAll('h2')
    const h2Arr = []
    h2s.forEach(el => {
      const text = el.textContent?.trim()
      if (text && text.length > 2 && text.length < 200) {
        h2Arr.push(text)
      }
    })
    seoH2s.value = h2Arr.slice(0, 10)
    
    // Text paragraphs
    const ps = doc.querySelectorAll('p')
    const texts = []
    ps.forEach(el => {
      const text = el.textContent?.trim()
      if (text && text.length > 30 && text.length < 500) {
        texts.push(text)
      }
    })
    seoTexts.value = texts.slice(0, 8)
    
    console.log('[WCLoner SEO] Extracted:', seoTitle.value, seoH1.value)
  } catch (e) {
    console.log('[WCLoner SEO] Cannot extract (cross-origin):', e)
  }
}

// Установка meta тега
function setMetaTag(name, content, attribute = 'name') {
  if (!content) return
  let el = document.querySelector(`meta[${attribute}="${name}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attribute, name)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

// Обновление URL браузера при навигации в iframe
function updateBrowserUrl(iframePath) {
  try {
    let pagePath = iframePath
      .replace('/__raw/', '')
      .replace('/__raw', '')
      .replace(/^\//, '')
    
    const currentUrl = new URL(window.location.href)
    if (pagePath) {
      currentUrl.searchParams.set('page', pagePath)
    } else {
      currentUrl.searchParams.delete('page')
    }
    
    window.history.replaceState({}, '', currentUrl.toString())
  } catch (e) {
    console.error('[WCLoner] Error updating URL:', e)
  }
}

// Обработка загрузки iframe
function onIframeLoad() {
  try {
    const iframe = iframeRef.value
    if (iframe && iframe.contentWindow) {
      const path = iframe.contentWindow.location.pathname
      console.log('[WCLoner] Iframe loaded:', path)
      // Не перезаписываем URL при первой загрузке - page уже установлен из URL
      if (initialLoad.value) {
        initialLoad.value = false
      } else {
        updateBrowserUrl(path)
      }
      
      // Извлечение SEO через небольшую задержку
      setTimeout(extractSEO, 300)
      
      // Инжекция tracking-sdk если есть настройки
      if (props.landing?.settings?.ads?.enable_tracking) {
        injectTracking()
      }
    }
  } catch (e) {
    console.log('[WCLoner] Cannot access iframe (cross-origin):', e)
  }
}

// Инжекция трекинга в iframe
function injectTracking() {
  try {
    const iframe = iframeRef.value
    if (!iframe || !iframe.contentDocument) return
    
    const doc = iframe.contentDocument
    
    // Tracking SDK
    const trackingScript = doc.createElement('script')
    trackingScript.src = '/tracking-sdk.js'
    trackingScript.onload = function() {
      console.log('[WCLoner] Tracking SDK loaded')
    }
    doc.body.appendChild(trackingScript)
  } catch (e) {
    console.log('[WCLoner] Cannot inject tracking (cross-origin):', e)
  }
}

// Слушатель сообщений от iframe
function handleMessage(event) {
  if (event.data && event.data.type === 'WCLONER_NAVIGATION') {
    console.log('[WCLoner] Navigation message:', event.data.path)
    updateBrowserUrl(event.data.path)
  }
}

onMounted(() => {
  window.addEventListener('message', handleMessage)
})

onUnmounted(() => {
  window.removeEventListener('message', handleMessage)
})
</script>

<template>
  <div class="wcloner-wrapper">
    <iframe
      ref="iframeRef"
      :src="iframeSrc"
      frameborder="0"
      allowfullscreen
      class="wcloner-iframe"
      @load="onIframeLoad"
    ></iframe>
    
    <!-- Hidden SEO content for crawlers -->
    <div class="seo-content" aria-hidden="true">
      <h1 v-if="seoH1">{{ seoH1 }}</h1>
      <h2 v-for="(h2, i) in seoH2s" :key="'h2-' + i">{{ h2 }}</h2>
      <p v-for="(text, i) in seoTexts" :key="'p-' + i">{{ text }}</p>
      <p v-if="seoDescription">{{ seoDescription }}</p>
    </div>
  </div>
</template>

<style scoped>
.wcloner-wrapper {
  width: 100%;
  height: 100vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
  position: relative;
}

.wcloner-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

/* Hidden SEO content - visible to crawlers but not users */
.seo-content {
  position: absolute;
  left: -9999px;
  top: -9999px;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}
</style>
