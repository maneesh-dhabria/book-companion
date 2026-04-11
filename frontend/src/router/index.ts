import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'library',
      component: () => import('@/views/LibraryView.vue'),
    },
    {
      path: '/books/:id',
      name: 'book-detail',
      component: () => import('@/views/BookDetailView.vue'),
    },
    {
      path: '/books/:id/sections/:sectionId',
      name: 'section-detail',
      component: () => import('@/views/BookDetailView.vue'),
    },
    {
      path: '/books/:id/sections/:sectionId/eval',
      name: 'eval-detail',
      component: () => import('@/views/EvalDetailView.vue'),
    },
    {
      path: '/books/:id/summary',
      name: 'book-summary',
      component: () => import('@/views/BookSummaryView.vue'),
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/views/SearchResultsView.vue'),
    },
    {
      path: '/annotations',
      name: 'annotations',
      component: () => import('@/views/AnnotationsView.vue'),
    },
    {
      path: '/concepts',
      name: 'concepts',
      component: () => import('@/views/ConceptsView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
    },
    {
      path: '/settings/:section',
      name: 'settings-section',
      component: () => import('@/views/SettingsView.vue'),
    },
    {
      path: '/upload',
      name: 'upload',
      component: () => import('@/views/UploadView.vue'),
    },
  ],
})

export default router
