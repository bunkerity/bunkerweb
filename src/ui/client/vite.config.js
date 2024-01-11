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
    },
  },
  build: {
    outDir: "../static",
    emptyOutDir: "../static",
    rollupOptions: {
      input: {
        home: resolve(__dirname, "./src/pages/home/index.html"),
        bans: resolve(__dirname, "./src/pages/bans/index.html"),
        configs: resolve(__dirname, "./src/pages/configs/index.html"),
        "global-config": resolve(
          __dirname,
          "./src/pages/global-config/index.html"
        ),
        instances: resolve(__dirname, "./src/pages/instances/index.html"),
        jobs: resolve(__dirname, "./src/pages/jobs/index.html"),
        login: resolve(__dirname, "./src/pages/login/index.html"),
        plugs: resolve(__dirname, "./src/pages/plugins/index.html"),
        services: resolve(__dirname, "./src/pages/services/index.html"),
        actions: resolve(__dirname, "./src/pages/actions/index.html"),
        account: resolve(__dirname, "./src/pages/account/index.html"),
      },
    },
  },
});
