import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API and thumbnails are served by the Python app; proxy them in dev so
// the browser only ever talks to one origin.
const API = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': API,
      '/thumbs': API,
    },
  },
})
