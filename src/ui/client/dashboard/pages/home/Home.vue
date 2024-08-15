<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderHome from "@components/Builder/Home.vue";
import { useGlobal } from "@utils/global";

/**
*  @name Page/Home.vue
*  @description This component is the home page.
  This page displays an overview of multiple stats related to BunkerWeb.
*/

const home = reactive({
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
  home.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderHome v-if="home.builder" :builder="home.builder" />
  </DashboardLayout>
</template>
