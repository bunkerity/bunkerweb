import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { viteSingleFile } from "vite-plugin-singlefile";
import { resolve } from "path";

export default defineConfig({
  plugins: [vue(), viteSingleFile()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "../../client/src"),
      "@store": resolve(__dirname, "../../client/src/store"),
      "@utils": resolve(__dirname, "../../client/src/utils"),
      "@layouts": resolve(__dirname, "../../client/src/layouts"),
      "@pages": resolve(__dirname, "../../client/src/pages"),
      "@components": resolve(__dirname, "../../client/src/components"),
      "@assets": resolve(__dirname, "../../client/src/assets"),
      "@lang": resolve(__dirname, "../../client/src/lang"),
      "@public": resolve(__dirname, "../../client/public"),
      "@pinia": resolve(__dirname, "../../client/node_modules/pinia"),
    },
  },
  build: {
    outDir: "./build",
    emptyOutDir: "./build",
  },
});
