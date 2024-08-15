<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderBans from "@components/Builder/Bans.vue";
import { useGlobal } from "@utils/global.js";
import { useDisplayStore } from "@store/global.js";

/**
 *  @name Page/Bans.vue
 *  @description This component is the bans page.
 */

// Set default store
const displayStore = useDisplayStore();
displayStore.setDisplay("main", 0);

const bans = reactive({
  builder: "",
});

onBeforeMount(() => {
  // Get builder data
  const dataAtt = "data-server-builder";
  const dataEl = document.querySelector(`[${dataAtt}]`);
  const data =
    dataEl && !dataEl.getAttribute(dataAtt).includes(dataAtt)
      ? JSON.parse(atob(dataEl.getAttribute(dataAtt)))
      : {};
  bans.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderBans v-if="bans.builder" :builder="bans.builder" />
  </DashboardLayout>
</template>
