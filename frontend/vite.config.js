import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = `http://${process.env.CLEAPYFLY_BACKEND_HOST || "127.0.0.1"}:${process.env.CLEAPYFLY_BACKEND_PORT || "8734"}`;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      "/media": { target: backend, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
  },
});
