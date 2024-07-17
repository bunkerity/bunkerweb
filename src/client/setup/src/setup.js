import { createApp } from "vue";
import Setup from "./Setup.vue";
import { getI18n } from "@utils/lang.js";
import "@public/css/style.css";
import "@public/css/flag-icons.min.css";

createApp(Setup)
  .use(getI18n(["setup", "action", "inp", "icons"]))
  .mount("#app");
