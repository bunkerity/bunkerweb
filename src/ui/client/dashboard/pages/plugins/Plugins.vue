<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderPlugins from "@components/Builder/Plugins.vue";
import { useGlobal } from "@utils/global.js";

/**
*  @name Page/PLugins.vue
*  @description This component is the plugin page.
  This page displays global information about plugins, and allow to delete or upload some plugins.
*/

const plugins = reactive({
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
  plugins.builder = data;
});

onMounted(() => {
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderPlugins v-if="plugins.builder" :builder="plugins.builder" />
  </DashboardLayout>
</template>
