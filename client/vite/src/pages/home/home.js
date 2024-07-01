import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Home from "./Home.vue";

const pinia = createPinia();

createApp(Home)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "home"]))
  .mount("#app");
