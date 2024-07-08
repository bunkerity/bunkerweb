<script setup>
import { reactive, onBeforeMount } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderGlobalConfig from "@components/Builder/GlobalConfig.vue";

/**
  @name Page/GlobalConfig.vue
  @description This component is the global config page.
  This page displays the global configuration of the server and allow to manage it.
*/

const globalConfig = reactive({
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
  globalConfig.builder = data;
});
</script>

<template>
  <DashboardLayout>
    <BuilderGlobalConfig
      v-if="globalConfig.builder"
      :builder="globalConfig.builder"
    />
  </DashboardLayout>
</template>
