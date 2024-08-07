import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Logs from "./Logs.vue";

const pinia = createPinia();

createApp(Logs)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "logs"]))
  .mount("#app");
