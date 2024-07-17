import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { viteSingleFile } from "vite-plugin-singlefile";
import { resolve } from "path";

export default defineConfig({
  plugins: [vue(), viteSingleFile()],
  resolve: {
    alias: {
      "@store": resolve(__dirname, "../dashboard/src/store"),
      "@utils": resolve(__dirname, "../dashboard/src/utils"),
      "@layouts": resolve(__dirname, "../dashboard/src/layouts"),
      "@components": resolve(__dirname, "../dashboard/src/components"),
      "@assets": resolve(__dirname, "../dashboard/src/assets"),
      "@lang": resolve(__dirname, "../dashboard/src/lang"),
      "@public": resolve(__dirname, "../dashboard/public"),
    },
  },
  build: {
    outDir: "./output",
    emptyOutDir: "./output",
  },
});
