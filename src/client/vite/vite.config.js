import { resolve } from "path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 3000,
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
      "@store": resolve(__dirname, "./src/store"),
      "@utils": resolve(__dirname, "./src/utils"),
      "@layouts": resolve(__dirname, "./src/layouts"),
      "@pages": resolve(__dirname, "./src/pages"),
      "@components": resolve(__dirname, "./src/components"),
      "@assets": resolve(__dirname, "./src/assets"),
      "@lang": resolve(__dirname, "./src/lang"),
      "@public": resolve(__dirname, "./public"),
    },
  },
  build: {
    chunkSizeWarningLimit: 1024,
    outDir: "../static",
    emptyOutDir: "../static",
    rollupOptions: {
      input: {
        home: resolve(__dirname, "./src/pages/home/index.html"),
      },
    },
  },
});
