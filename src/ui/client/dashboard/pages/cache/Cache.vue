<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderCache from "@components/Builder/Cache.vue";
import { useGlobal } from "@utils/global.js";

/**
*  @name Page/Cache.vue
*  @description This component is the cache page.
  This page displays global information about cache, and allow to download a cache file.
*/

const cache = reactive({
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
  cache.builder = data;
});

onMounted(() => {
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderCache v-if="cache.builder" :builder="cache.builder" />
  </DashboardLayout>
</template>
