import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Reports from "./reports.vue";

const pinia = createPinia();

createApp(Reports)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "reports"]))
  .mount("#app");
