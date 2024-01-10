import { createApp } from "vue";
import Totp from "./Totp.vue";
import { getI18n } from "@utils/lang.js";

createApp(Totp)
  .use(getI18n(["totp"]))
  .mount("#app");
