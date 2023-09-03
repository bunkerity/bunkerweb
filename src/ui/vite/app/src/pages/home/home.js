import { createApp } from "vue";
import Home from "./Home.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(Home).use(pinia).mount("#app");
