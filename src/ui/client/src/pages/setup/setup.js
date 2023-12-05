import { createApp } from "vue";
import Setup from "./Setup.vue";
import { getI18n } from "@utils/lang.js";

createApp(Setup)
  .use(getI18n(["setup"]))
  .mount("#app");
