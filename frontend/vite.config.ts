import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// In development the API is proxied so the browser talks to one origin; this
// keeps the HttpOnly refresh cookie first-party (no third-party cookie issues).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_PROXY_TARGET || 'http://localhost:8000';
  return {
    plugins: [react()],
    server: { proxy: { '/api': { target, changeOrigin: false } } },
    preview: { proxy: { '/api': { target, changeOrigin: false } } },
  };
});
