import { createApp } from "vue";
import Instances from "./Instances.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Instances)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "inp", "instances"]))
  .mount("#app");
