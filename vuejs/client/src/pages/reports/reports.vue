<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderReports from "@components/Builder/Reports.vue";
import { useGlobal } from "@utils/global.js";
import { useForm } from "@utils/form.js";

/**
  @name Page/Reports.vue
  @description This component is the report page.
  This page displays global information about reports, and allow to delete or upload some reports.
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
      ? JSON.parse(dataEl.getAttribute(dataAtt))
      : {};
  reports.builder = data;
});

onMounted(() => {
  useGlobal();
  useForm();
});

const builder = [
  {
    type: "void",
    widgets: [
      {
        type: "MessageUnmatch",
        data: {
          text: "reports_not_found",
        },
      },
    ],
  },
];
</script>

<template>
  <DashboardLayout>
    <BuilderReports v-if="builder" :builder="builder" />
  </DashboardLayout>
</template>
