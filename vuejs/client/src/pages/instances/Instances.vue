<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import Builder from "@components/Builder.vue";
import { useGlobal } from "@utils/global.js";

/**
  @name Page/Home.vue
  @description This component is the home page.
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
      ? JSON.parse(dataEl.getAttribute(dataAtt))
      : {};
  home.builder = data;
});

onMounted(() => {
  useGlobal();
});

// const data = [
// {
//         type: "Instance",
//         data: {
//           details: [
//             { key: <instances_hostname="hostname">, value: "www.example.com" },
//             { key: <instances_method="method">, value: <dashboard_ui> or <dashboard_scheduler>...},
//             { key: <instances_port="port">, value: "1084" },
//             { key: <instances_status="status">, value: <instances_active="active"> or <instances_inactive="inactive"> },
//           ],
//           status: "success",
//           title: "www.example.com",
//           buttons: [
//             {
//               text: <action_*>,
//               color: "edit",
//               size: "normal",
//             },
//           ],
//         },
//       },
// ];
</script>

<template>
  <DashboardLayout>
    <Builder v-if="home.builder" :builder="home.builder" />
    <div id="test-el"></div>
  </DashboardLayout>
</template>
