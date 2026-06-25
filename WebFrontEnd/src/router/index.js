import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import PostureUpload from '../views/PostureUpload.vue'
import TongueProcess from '../views/TongueProcess.vue'
import JointReport from '../views/JointReport.vue'
import HistoryAnalysis from '../views/HistoryAnalysis.vue'
import History from '../views/History.vue'
import MetricGuide from '../views/MetricGuide.vue'
import DemoVideo from '../views/DemoVideo.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: Login },
  { path: '/profile', redirect: '/posture' },
  { path: '/posture', name: 'posture', component: PostureUpload, meta: { requiresAuth: true } },
  { path: '/demo-video', name: 'demo-video', component: DemoVideo, meta: { requiresAuth: true } },
  { path: '/tongue', name: 'tongue', component: TongueProcess, meta: { requiresAuth: true } },
  { path: '/joint-report', name: 'joint-report', component: JointReport, meta: { requiresAuth: true } },
  { path: '/metric-guide', name: 'metric-guide', component: MetricGuide, meta: { requiresAuth: true } },
  { path: '/history-analysis', name: 'history-analysis', component: HistoryAnalysis, meta: { requiresAuth: true } },
  { path: '/history', name: 'history', component: History, meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const FIRST_VISIT_KEY = 'mask_first_visit_in_tab'

router.beforeEach((to) => {
  const isFirstVisitInTab = !sessionStorage.getItem(FIRST_VISIT_KEY)
  if (isFirstVisitInTab) {
    sessionStorage.setItem(FIRST_VISIT_KEY, '1')
    localStorage.removeItem('mask_token')
    localStorage.removeItem('mask_user_id')
    localStorage.removeItem('mask_display_name')
    if (to.path !== '/login') {
      return '/login'
    }
  }

  const token = localStorage.getItem('mask_token')
  if (to.meta.requiresAuth && !token) {
    return '/login'
  }

  return true
})

export default router
