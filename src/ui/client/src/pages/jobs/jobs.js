import { createApp } from "vue";
import Jobs from "./Jobs.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Jobs)
  .use(pinia)
  .use(getI18n(["jobs", "dashboard", "custom_inputs"]))
  .mount("#app");
