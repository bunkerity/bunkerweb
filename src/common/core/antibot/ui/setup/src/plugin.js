import { createApp } from "vue";
import Plugin from "./Plugin.vue";
import { getI18n } from "@utils/lang.js";
import "@public/css/style.css";
import "@public/css/flag-icons.min.css";

createApp(Plugin)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "plugins", "inp"]))
  .mount("#app");
