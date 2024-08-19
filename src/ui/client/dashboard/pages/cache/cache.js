import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Cache from "./Cache.vue";

const pinia = createPinia();

createApp(Cache)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "cache"]))
  .mount("#app");
