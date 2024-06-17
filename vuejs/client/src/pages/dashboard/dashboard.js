import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Dashboard from "./Dashboard.vue";

const pinia = createPinia();

createApp(Dashboard)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "bans", "inp", "icons"]))
  .mount("#app");
