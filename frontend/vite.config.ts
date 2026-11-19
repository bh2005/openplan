import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'OpenPlan',
        short_name: 'OpenPlan',
        description: 'Open-Source-Projektplanung mit Gantt, Abhängigkeiten und kritischem Pfad',
        theme_color: '#1f6feb',
        background_color: '#0f1419',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/docs/, /^\/openapi\.json/],      // Swagger darf nicht von der SPA-Hülle überdeckt werden
        runtimeCaching: [
          {
            urlPattern: ({ url }: { url: URL }) => url.pathname.startsWith('/api/') && url.pathname !== '/api/auth/login',
            handler: 'NetworkFirst',
            method: 'GET',
            options: { cacheName: 'openplan-api', networkTimeoutSeconds: 4, expiration: { maxEntries: 50, maxAgeSeconds: 7 * 86400 } },
          },
        ],
      },
    }),
  ],
  server: { port: 5173, watch: process.env.VITE_POLL ? { usePolling: true, interval: 300 } : undefined, proxy: Object.fromEntries(['/api', '/docs', '/docs-assets', '/openapi.json'].map(p => [p, process.env.API_URL || 'http://localhost:8765'])) },
})
