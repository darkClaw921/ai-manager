import { defineConfig, Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

const DEFAULT_APP_URL = 'http://localhost:3000'

function seoPlugin(): Plugin {
  const appUrl = (process.env.VITE_APP_URL || DEFAULT_APP_URL).replace(/\/+$/, '')

  return {
    name: 'vite-plugin-seo',

    // Replace %VITE_APP_URL% placeholders in index.html
    transformIndexHtml(html) {
      return html.replace(/%VITE_APP_URL%/g, appUrl)
    },

    // Generate sitemap.xml and robots.txt at build time
    generateBundle() {
      const now = new Date().toISOString().split('T')[0]

      const sitemap = [
        { url: '/', changefreq: 'weekly', priority: '1.0' },
        { url: '/register', changefreq: 'monthly', priority: '0.8' },
        { url: '/login', changefreq: 'monthly', priority: '0.5' },
      ]

      const sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemap.map(({ url, changefreq, priority }) => `  <url>
    <loc>${appUrl}${url}</loc>
    <lastmod>${now}</lastmod>
    <changefreq>${changefreq}</changefreq>
    <priority>${priority}</priority>
  </url>`).join('\n')}
</urlset>`

      const robotsTxt = `User-agent: *
Allow: /
Allow: /register
Allow: /login

Disallow: /dashboard
Disallow: /leads
Disallow: /conversations
Disallow: /scripts
Disallow: /channels
Disallow: /bookings
Disallow: /settings
Disallow: /users
Disallow: /managers
Disallow: /onboarding
Disallow: /api/

Sitemap: ${appUrl}/sitemap.xml`

      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemapXml })
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: robotsTxt })
    },
  }
}

export default defineConfig({
  plugins: [react(), seoPlugin()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
