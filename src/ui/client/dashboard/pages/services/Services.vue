<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderServices from "@components/Builder/Services.vue";
import { useGlobal } from "@utils/global";

/**
*  @name Page/Services.vue
*  @description This component is the services page.
  This page displays services and forms to manage them.
*/

const services = reactive({
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
  services.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderServices v-if="services.builder" :builder="services.builder" />
  </DashboardLayout>
</template>
