<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderRaw from "@components/Builder/Raw.vue";
import { useGlobal } from "@utils/global";

/**
*  @name Page/Raw.vue
*  @description This component is the raw page.
  This page displays the raw form and additionnal actions to manage or create a service.
*/

const raw = reactive({
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
  raw.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <div class="col-span-12 grid grid-cols-12 card">
      <BuilderRaw v-if="raw.builder" :builder="raw.builder" />
    </div>
  </DashboardLayout>
</template>
