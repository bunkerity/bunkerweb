import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Configs from "./Configs.vue";

const pinia = createPinia();

createApp(Configs)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "configs"]))
  .mount("#app");
