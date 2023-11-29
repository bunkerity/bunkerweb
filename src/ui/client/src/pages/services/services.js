import { createApp } from "vue";
import Services from "./Services.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Services)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "services", "inp"]))
  .mount("#app");
