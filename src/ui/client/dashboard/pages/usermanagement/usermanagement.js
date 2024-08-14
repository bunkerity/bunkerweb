import { createApp } from "vue";
import { createPinia } from "pinia";
import { getI18n } from "@utils/lang.js";
import UserManagement from "./UserManagement.vue";

const pinia = createPinia();

createApp(UserManagement)
  .use(pinia)
  .use(getI18n(["dashboard", "action", "inp", "icons", "user_management"]))
  .mount("#app");
