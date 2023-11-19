import { createApp } from "vue";
import Actions from "./Actions.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Actions)
  .use(pinia)
  .use(getI18n(["actions", "dashboard"]))
  .mount("#app");
