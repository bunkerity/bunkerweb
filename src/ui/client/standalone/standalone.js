import { createApp } from "vue";
import standalone from "./Standalone.vue";
import { getI18n } from "@utils/lang.js";
import "@public/css/style.css";
import "@public/css/flag-icons.min.css";

createApp(standalone)
  .use(getI18n(["setup", "action", "inp", "icons"]))
  .mount("#app");
