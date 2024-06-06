import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import GlobalConfig from "./GlobalConfig.vue";

const pinia = createPinia();

createApp(GlobalConfig)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "global_config"]))
  .mount("#app");
