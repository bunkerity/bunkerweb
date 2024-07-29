import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Services from "./Services.vue";

const pinia = createPinia();

createApp(Services)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "services"]))
  .mount("#app");
