import { createApp } from "vue";
import Plugins from "./Plugins.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Plugins)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "plugins", "inp"]))
  .mount("#app");
