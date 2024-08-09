<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import BuilderSetup from "@components/Builder/Setup.vue";

/**
*  @name Page/Setup.vue
*  @description This component is the setup page.
  This page displays all steps to setup BunkerWeb.
*/

const setup = reactive({
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
  setup.builder = data;
});
</script>

<template>
  <DashboardLayout>
    <BuilderSetup v-if="setup.builder" :builder="setup.builder" />
  </DashboardLayout>
</template>
