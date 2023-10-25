import { createApp } from "vue";
import Instances from "./Instances.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(Instances).use(pinia).mount("#app");
