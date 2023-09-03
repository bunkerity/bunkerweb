import { createApp } from "vue";
import Services from "./Services.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(Services).use(pinia).mount("#app");
