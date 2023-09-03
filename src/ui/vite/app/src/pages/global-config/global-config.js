import { createApp } from "vue";
import GlobalConfig from "./GlobalConfig.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(GlobalConfig).use(pinia).mount("#app");
