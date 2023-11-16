import { createApp } from "vue";
import Plugins from "./Plugins.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Plugins)
  .use(pinia)
  .use(getI18n(["plugins", "dashboard"]))
  .mount("#app");
