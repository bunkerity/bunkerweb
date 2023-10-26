import { createApp } from "vue";
import Actions from "./Actions.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(Actions).use(pinia).mount("#app");
