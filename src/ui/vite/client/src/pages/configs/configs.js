import { createApp } from "vue";
import Configs from "./Configs.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(Configs).use(pinia).mount("#app");
