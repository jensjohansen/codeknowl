/**
 * Vite configuration for CodeKnowl Web UI
 * 
 * Why this exists:
 * - Build configuration for React application
 * - Supports TypeScript and Tailwind CSS
 * - Enables development server and production builds
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
