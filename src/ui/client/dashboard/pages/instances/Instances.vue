<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderInstances from "@components/Builder/Instances.vue";
import { useGlobal } from "@utils/global.js";
import { useDisplayStore } from "@store/global.js";

/**
*  @name Page/Instances.vue
*  @description This component is the instances page.
  This page displays current instances and allows to manage them.
  We are using displayStore and setting ["main", 1] to display the instances list first.
*/

// Set default store
const displayStore = useDisplayStore();
displayStore.setDisplay("main", 1);

const instances = reactive({
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
  instances.builder = data;
});

onMounted(() => {
  // Set the page title
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
    <BuilderInstances v-if="instances.builder" :builder="instances.builder" />
  </DashboardLayout>
</template>
