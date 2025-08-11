import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  // In production (vite build), serve assets from /frontend/
  // so URLs like /frontend/assets/* match the deployed paths on Vercel
  base: command === 'build' ? '/frontend/' : '/',
  plugins: [react()],
}))
