<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderInstances from "@components/Builder/Instances.vue";
import { useGlobal } from "@utils/global.js";
import { useDisplayStore } from "@store/global.js";

/**
*  @name Page/Instances.vue
*  @description This component is the instances page.
  This page displays current instances and allows to manage them.
  We are using displayStore and setting ["main", 1] to display the instances list first.
*/

// Set default store
const displayStore = useDisplayStore();
displayStore.setDisplay("main", 0);

const instances = reactive({
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
  instances.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderInstances v-if="instances.builder" :builder="instances.builder" />
  </DashboardLayout>
</template>
