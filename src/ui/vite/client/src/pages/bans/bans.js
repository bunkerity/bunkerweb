import { createApp } from "vue";
import Bans from "./Bans.vue";
import { createPinia } from "pinia";
const pinia = createPinia();

createApp(Bans).use(pinia).mount("#app");
