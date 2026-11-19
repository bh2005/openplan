import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { restoreSession, state } from './lib/store'
import { t } from './lib/i18n'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
    { path: '/', component: () => import('./views/ProjectsView.vue') },
    { path: '/project/:id(\\d+)', component: () => import('./views/ProjectView.vue') },
    { path: '/reports/:id(\\d+)?', component: () => import('./views/ReportView.vue') },
    { path: '/todo', component: () => import('./views/TodoView.vue') },
    { path: '/dashboard', component: () => import('./views/DashboardView.vue') },
    { path: '/org', component: () => import('./views/OrgView.vue') },
    { path: '/overview', component: () => import('./views/OverviewView.vue') },
    { path: '/absences', component: () => import('./views/MyAbsencesView.vue') },
    { path: '/templates', component: () => import('./views/TemplatesView.vue') },
    { path: '/admin', component: () => import('./views/AdminView.vue') },
    { path: '/help/:id?', component: () => import('./views/HelpView.vue') },
    { path: '/:rest(.*)*', redirect: '/' },
  ],
})

let restored = false
router.beforeEach(async to => {
  if (!restored) { await restoreSession(); restored = true }
  if (!to.meta.public && !state.user) return { path: '/login', query: { next: to.fullPath } }
  if (to.path === '/login' && state.user) return '/'
})

const app = createApp(App)
app.config.globalProperties.$t = t
app.use(router).mount('#app')
