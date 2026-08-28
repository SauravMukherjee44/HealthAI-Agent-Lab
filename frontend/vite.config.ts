import { defineConfig } from "vite";

export default defineConfig({
  publicDir: "public",
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "^/health$": "http://127.0.0.1:8000",
    },
  },
});
