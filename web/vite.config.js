import { defineConfig } from 'vite';

// base relativo: a pasta dist/ funciona em qualquer subcaminho (GitHub Pages, por exemplo).
export default defineConfig({
  base: './',
  build: { target: 'es2022', chunkSizeWarningLimit: 900 },
});
