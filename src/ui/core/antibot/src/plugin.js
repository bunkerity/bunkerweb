import { createApp } from "vue";
import Plugin from "./Plugin.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import "@public/css/style.css";
import "@public/css/flag-icons.min.css";

const pinia = createPinia();

createApp(Plugin)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "plugin", "antibot"]))
  .mount("#app");
