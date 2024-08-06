import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Modes from "./Modes.vue";

const pinia = createPinia();

createApp(Modes)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "services", "raw"]))
  .mount("#app");
