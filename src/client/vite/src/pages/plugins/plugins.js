import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Plugins from "./Plugins.vue";

const pinia = createPinia();

createApp(Plugins)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "plugins"]))
  .mount("#app");
