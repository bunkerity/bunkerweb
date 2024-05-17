import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Builder from "./Builder.vue";

const pinia = createPinia();

createApp(Builder)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "bans", "inp"]))
  .mount("#app");