import { createApp } from "vue";
import Login from "./Login.vue";
import { getI18n } from "@utils/lang.js";

createApp(Login)
  .use(getI18n(["login", "action", "inp"]))
  .mount("#app");
