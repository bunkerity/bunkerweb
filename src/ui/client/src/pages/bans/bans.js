import { createApp } from "vue";
import Bans from "./Bans.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Bans)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "bans", "inp"]))
  .mount("#app");
