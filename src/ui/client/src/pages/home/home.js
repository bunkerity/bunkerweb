import { createApp } from "vue";
import Home from "./Home.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Home)
  .use(pinia)
  .use(getI18n(["home", "dashboard"]))
  .mount("#app");
