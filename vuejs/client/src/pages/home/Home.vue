<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderHome from "@components/Builder/Home.vue";
import { useGlobal } from "@utils/global.js";
import { useForm } from "@utils/form.js";

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
  useForm();
});

// const data = [
//   {
//     type: "card",
//     link : "https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui"
//     containerColumns: { pc: 4, tablet: 6, mobile: 12 },
//     widgets: [
//       {
//         type: "Stat",
//         data: {
//           title: "home_version",
//           subtitle: "home_all_features_available" if is_pro_version else "home_upgrade_pro",
//           subtitleColor: "success" is is_pro_version else "warning",
//           stat: "home_pro" if is_pro_version else "home_free",
//           iconName: "crown" if is_pro_version else "core",
//           iconColor: "amber",
//         },
//       },
//     ],
//   },
//   {
//     type: "card",
//     link: "https://github.com/bunkerity/bunkerweb",
//     containerColumns: { pc: 4, tablet: 6, mobile: 12 },
//     widgets: [
//       {
//         type: "Stat",
//         data: {
//           title: "home_version_number",
//           subtitle: "home_latest_version" if is_latest_version else "home_upgrade_available",
//           subtitleColor: "success" if is_latest_version else "warning",
//           stat: <current_version>,
//           iconName: "wire",
//           iconColor: "teal",
//         },
//       },
//     ],
//   },
//   {
//     type: "card",
//     link: "/instances",
//     containerColumns: { pc: 4, tablet: 6, mobile: 12 },
//     widgets: [
//       {
//         type: "Stat",
//         data: {
//           title: "home_instances",
//           subtitle: "home_total_number",
//           subtitleColor: "info",
//           stat: "<instances_total>",
//           iconName: "box",
//           iconColor: "dark",
//         },
//       },
//     ],
//   },
//   {
//     type: "card",
//     link: "/services",
//     containerColumns: { pc: 4, tablet: 6, mobile: 12 },
//     widgets: [
//       {
//         type: "Stat",
//         data: {
//           title: "home_services",
//           subtitle: "home_all_methods_included",
//           subtitleColor: "info",
//           stat: "<services_total>",
//           iconName: "disk",
//           iconColor: "orange",
//         },
//       },
//     ],
//   },
//   {
//     type: "card",
//     link: "/plugins",
//     containerColumns: { pc: 4, tablet: 6, mobile: 12 },
//     widgets: [
//       {
//         type: "Stat",
//         data: {
//           title: "home_plugins",
//           subtitle: "home_no_error" if all_plugins_ok else "home_errors_found",
//           subtitleColor: "success" if all_plugins_ok else "error",
//           stat: "<plugins_total>",
//           iconName: "puzzle",
//           iconColor: "yellow",
//         },
//       },
//     ],
//   },
// ];
</script>

<template>
  <DashboardLayout>
    <BuilderHome v-if="home.builder" :builder="home.builder" />
  </DashboardLayout>
</template>
