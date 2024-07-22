import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { viteSingleFile } from "vite-plugin-singlefile";
import VueI18nPlugin from "@intlify/unplugin-vue-i18n/vite";
import { resolve } from "path";

export default defineConfig({
  plugins: [
    vue(),
    viteSingleFile(),
    VueI18nPlugin({
      include: resolve(__dirname, "./src/lang/**"),
      jitCompilation: true,
    }),
  ],
  resolve: {
    alias: {
      "@store": resolve(__dirname, "./dashboard/store"),
      "@utils": resolve(__dirname, "./dashboard/utils"),
      "@layouts": resolve(__dirname, "./dashboard/layouts"),
      "@components": resolve(__dirname, "./dashboard/components"),
      "@assets": resolve(__dirname, "./dashboard/assets"),
      "@lang": resolve(__dirname, "./dashboard/lang"),
      "@public": resolve(__dirname, "./public"),
    },
  },
  build: {
    outDir: "./opt-setup",
    emptyOutDir: "./opt-setup",
    rollupOptions: {
      input: {
        setup: resolve(__dirname, "./setup/index.html"),
      },
    },
  },
});
