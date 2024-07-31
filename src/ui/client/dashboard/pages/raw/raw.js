import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Raw from "./Raw.vue";

const pinia = createPinia();

createApp(Raw)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "services", "raw"]))
  .mount("#app");
