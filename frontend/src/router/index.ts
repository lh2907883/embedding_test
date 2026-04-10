import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'tenants',
      component: () => import('@/views/TenantList.vue'),
    },
    {
      path: '/tenant/:tenantId',
      name: 'tenant-detail',
      component: () => import('@/views/TenantDetail.vue'),
      props: true,
    },
    {
      path: '/tenant/:tenantId/search',
      name: 'search',
      component: () => import('@/views/SearchView.vue'),
      props: true,
    },
  ],
})

export default router
