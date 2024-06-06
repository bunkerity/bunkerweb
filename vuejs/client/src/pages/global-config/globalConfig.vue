<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import Builder from "@components/Builder.vue";
import Advanced from "@components/Forms/Type/Advanced.vue";
import { useGlobal } from "@utils/global.js";
import { useForm } from "@utils/form.js";

/**
  @name Page/GlobalConfig.vue
  @description This component is the gllobal config page.
  This page displays an overview of multiple stats related to BunkerWeb.
*/

const globalConfig = reactive({
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
  globalConfig.builder = data;
});

onMounted(() => {
  useGlobal();
  useForm();
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

const data = [
  {
    name: "plugin name",
    type: "pro",
    is_activate: true,
    description: "plugin description",
    page: "/page",
    settings: [
      {
        columns: { pc: 4, tablet: 6, mobile: 12 },
        id: "test-check",
        value: "yes",
        label: "Checkbox",
        name: "checkbox",
        required: true,
        hideLabel: false,
        inpType: "checkbox",
      },
      {
        columns: { pc: 4, tablet: 6, mobile: 12 },
        id: "test-input",
        value: "yes",
        type: "text",
        name: "test-input",
        disabled: false,
        required: true,
        label: "Test input",
        pattern: "(test)",
        inpType: "input",
      },
      {
        columns: { pc: 4, tablet: 6, mobile: 12 },
        id: "test-select",
        value: "yes",
        values: ["yes", "no"],
        name: "test-select",
        disabled: false,
        required: true,
        requiredValues: ["no"], // need required to be checked
        label: "Test select",
        inpType: "select",
      },
    ],
  },
];
</script>

<template>
  <DashboardLayout>
    <Advanced :plugins="data" />
  </DashboardLayout>
</template>
