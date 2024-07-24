import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Jobs from "./Jobs.vue";

const pinia = createPinia();

createApp(Jobs)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "jobs"]))
  .mount("#app");
