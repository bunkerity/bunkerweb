import { createApp } from "vue";
import Plugins from "./Plugins.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(Plugins).use(pinia).mount("#app");
