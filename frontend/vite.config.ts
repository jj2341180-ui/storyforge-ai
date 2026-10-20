import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development /api is proxied to the local FastAPI service (see SETUP.md).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.STORYFORGE_API || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
