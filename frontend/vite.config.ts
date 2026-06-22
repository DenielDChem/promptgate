import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

// Built output is served by the FastAPI backend via StaticFiles (see
// docs/PLATFORM_ARCHITECTURE.md §1). base '' keeps asset URLs same-origin-relative.
export default defineConfig({
  base: '',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Split the (large but cacheable) Monaco editor into its own chunk so
        // it doesn't bloat the app entry and is cached across deploys (P2).
        manualChunks(id) {
          if (id.includes('node_modules/monaco-editor')) return 'monaco';
        },
      },
    },
  },
});
