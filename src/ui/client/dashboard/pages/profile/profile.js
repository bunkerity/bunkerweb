import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import Profile from "./Profile.vue";

const pinia = createPinia();

createApp(Profile)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "profile"]))
  .mount("#app");
