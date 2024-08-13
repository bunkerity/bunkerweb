<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderReports from "@components/Builder/Reports.vue";
import { useGlobal } from "@utils/global";

/**
*  @name Page/Reports.vue
*  @description This component is the reports page.
  This page displays reports and forms to manage them.
*/

const reports = reactive({
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
  reports.builder = data;
});

onMounted(() => {
  // Set the page title
  useGlobal();
});
</script>

<template>
  <DashboardLayout>
    <BuilderReports v-if="reports.builder" :builder="reports.builder" />
  </DashboardLayout>
</template>
