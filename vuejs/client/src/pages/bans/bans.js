import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Bans from "./Bans.vue";

const pinia = createPinia();

createApp(Bans)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "bans"]))
  .mount("#app");
