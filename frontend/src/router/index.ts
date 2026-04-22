import { createRouter, createWebHistory } from 'vue-router'

const APP_NAME = 'Book Companion'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'library',
      meta: { title: 'Library' },
      component: () => import('@/views/LibraryView.vue'),
    },
    {
      path: '/books/:id',
      name: 'book-detail',
      meta: { title: 'Reader' },
      component: () => import('@/views/BookDetailView.vue'),
    },
    {
      path: '/books/:id/sections/:sectionId',
      name: 'section-detail',
      meta: { title: 'Reader' },
      component: () => import('@/views/BookDetailView.vue'),
    },
    {
      path: '/books/:id/sections/:sectionId/eval',
      name: 'eval-detail',
      meta: { title: 'Eval Details' },
      component: () => import('@/views/EvalDetailView.vue'),
    },
    {
      path: '/books/:id/summary',
      name: 'book-summary',
      meta: { title: 'Book Summary' },
      component: () => import('@/views/BookSummaryView.vue'),
    },
    {
      path: '/search',
      name: 'search',
      meta: { title: 'Search' },
      component: () => import('@/views/SearchResultsView.vue'),
    },
    {
      path: '/annotations',
      name: 'annotations',
      meta: { title: 'Annotations' },
      component: () => import('@/views/AnnotationsView.vue'),
    },
    {
      path: '/concepts',
      name: 'concepts',
      meta: { title: 'Concepts' },
      component: () => import('@/views/ConceptsView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      meta: { title: 'Settings' },
      component: () => import('@/views/SettingsView.vue'),
    },
    {
      path: '/settings/:section',
      name: 'settings-section',
      meta: { title: 'Settings' },
      component: () => import('@/views/SettingsView.vue'),
    },
    {
      path: '/upload',
      name: 'upload',
      meta: { title: 'Upload' },
      component: () => import('@/views/UploadView.vue'),
    },
  ],
})

router.afterEach((to) => {
  const meta = to.meta as { title?: string }
  const title = meta.title
  document.title = title ? `${title} — ${APP_NAME}` : APP_NAME
})

export default router
