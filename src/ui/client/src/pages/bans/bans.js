import { createApp } from "vue";
import Bans from "./Bans.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Bans)
  .use(pinia)
  .use(getI18n(["bans", "dashboard", "A11y"]))
  .mount("#app");
