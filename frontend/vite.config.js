import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-Proxy: /api und /uploads gehen ans FastAPI-Backend auf :8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // auch von aussen erreichbar (Codespaces/LAN)
    allowedHosts: true, // Codespaces-Domains (*.app.github.dev) zulassen
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/uploads": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
