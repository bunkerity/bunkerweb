import { createApp } from "vue";
import Jobs from "./Jobs.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(Jobs).use(pinia).mount("#app");
