import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  root: resolve(import.meta.dirname, 'phone'),
  build: {
    outDir: resolve(import.meta.dirname, 'www'),
    emptyOutDir: true
  }
});
