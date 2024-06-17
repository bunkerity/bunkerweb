import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Test from "./Test.vue";

const pinia = createPinia();

createApp(Test)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "bans", "inp", "icons"]))
  .mount("#app");
