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
      "@pages": resolve(__dirname, "./src/pages"),
      "@components": resolve(__dirname, "./src/components"),
    },
  },
  build: {
    outDir: "../static",
    emptyOutDir: "../static",
    rollupOptions: {
      input: {
        test: resolve(__dirname, "./src/pages/test/index.html"),
      },
    },
  },
});
