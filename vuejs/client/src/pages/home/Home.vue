<script setup>
import { reactive, onBeforeMount } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import Builder from "@components/Builder.vue";

const home = reactive({
  builder : ""
})

onBeforeMount(() => {
  // Get builder data
  const dataAtt = 'data-server-builder';
  const dataEl = document.querySelector(`[${dataAtt}]`);
  const data = dataEl && !dataEl.getAttribute(dataAtt).includes(dataAtt) ? JSON.parse(dataEl.getAttribute(dataAtt)) : {};
  home.builder = data;
});
</script>

<template>
  <DashboardLayout >
    <Builder v-if="home.builder" :builder="home.builder" />
  </DashboardLayout>
</template>
