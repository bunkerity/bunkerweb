import { createApp } from "vue";
import Instances from "./Instances.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Instances)
  .use(pinia)
  .use(getI18n(["instances", "dashboard", "A11y"]))
  .mount("#app");
