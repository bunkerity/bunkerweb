import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { viteSingleFile } from "vite-plugin-singlefile";
import { resolve } from "path";

export default defineConfig({
  plugins: [vue(), viteSingleFile()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "../../../../../ui/client/src"),
      "@store": resolve(__dirname, "../../../../../ui/client/src/store"),
      "@utils": resolve(__dirname, "../../../../../ui/client/src/utils"),
      "@layouts": resolve(__dirname, "../../../../../ui/client/src/layouts"),
      "@pages": resolve(__dirname, "../../../../../ui/client/src/pages"),
      "@components": resolve(
        __dirname,
        "../../../../../ui/client/src/components"
      ),
      "@assets": resolve(__dirname, "../../../../../ui/client/src/assets"),
      "@lang": resolve(__dirname, "../../../../../ui/client/src/lang"),
      "@public": resolve(__dirname, "../../../../../ui/client/public"),
    },
  },
  build: {
    outDir: "../../ui",
  },
});
