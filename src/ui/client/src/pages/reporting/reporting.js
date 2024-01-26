import { createApp } from "vue";
import Reporting from "./Reporting.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Reporting)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "reporting"]))
  .mount("#app");
