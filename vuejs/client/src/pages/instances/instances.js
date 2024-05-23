import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Instances from "./Instances.vue";

const pinia = createPinia();

createApp(Instances)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "instances"]))
  .mount("#app");
