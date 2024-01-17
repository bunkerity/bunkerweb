import { createApp } from "vue";
import Sitemap from "./Sitemap.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Sitemap)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "sitemap"]))
  .mount("#app");
