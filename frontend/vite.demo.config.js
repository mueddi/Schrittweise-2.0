import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// Demo-Build: eine einzige HTML-Datei (JS/CSS/Fonts inline) mit Mock-Backend.
//   npx vite build --config vite.demo.config.js   -> dist-demo/index.html
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  define: { "import.meta.env.VITE_DEMO": JSON.stringify("1") },
  build: {
    outDir: "dist-demo",
    assetsInlineLimit: 100 * 1024 * 1024, // KaTeX-Fonts als data-URIs einbetten
    chunkSizeWarningLimit: 8000,
  },
});
