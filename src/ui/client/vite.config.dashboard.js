import { resolve } from "path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import VueI18nPlugin from "@intlify/unplugin-vue-i18n/vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    VueI18nPlugin({
      include: resolve(__dirname, "./dashboard/lang/**"),
      jitCompilation: true,
    }),
  ],
  server: {
    host: true,
    port: 3000,
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./dashboard"),
      "@store": resolve(__dirname, "./dashboard/store"),
      "@utils": resolve(__dirname, "./dashboard/utils"),
      "@layouts": resolve(__dirname, "./dashboard/layouts"),
      "@pages": resolve(__dirname, "./dashboard/pages"),
      "@components": resolve(__dirname, "./dashboard/components"),
      "@assets": resolve(__dirname, "./dashboard/assets"),
      "@lang": resolve(__dirname, "./dashboard/lang"),
      "@public": resolve(__dirname, "./public"),
    },
  },
  build: {
    chunkSizeWarningLimit: 1024,
    outDir: "./opt-dashboard",
    emptyOutDir: "./opt-dashboard",
    rollupOptions: {
      input: {
        home: resolve(__dirname, "./dashboard/pages/home/index.html"),
        instances: resolve(__dirname, "./dashboard/pages/instances/index.html"),
      },
    },
  },
});
