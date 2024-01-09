import { createApp } from "vue";
import Account from "./Account.vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";

const pinia = createPinia();

createApp(Account)
  .use(pinia)
  .use(getI18n(["dashboard", "api", "action", "account", "inp"]))
  .mount("#app");
