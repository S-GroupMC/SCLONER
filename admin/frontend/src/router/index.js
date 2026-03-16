import { createRouter, createWebHistory } from 'vue-router'
import LandingsView from '../views/LandingsView.vue'
import DownloadView from '../views/DownloadView.vue'
import SiteDetailsView from '../views/SiteDetailsView.vue'

const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    {
      path: '/',
      redirect: '/landings'
    },
    {
      path: '/landings',
      name: 'landings',
      component: LandingsView
    },
    {
      path: '/download',
      name: 'download',
      component: DownloadView
    },
    {
      path: '/site/:folder',
      name: 'site-details',
      component: SiteDetailsView
    }
  ]
})

export default router
