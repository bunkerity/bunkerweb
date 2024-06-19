<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderPlugins from "@components/Builder/Plugins.vue";
import { useGlobal } from "@utils/global.js";

/**
  @name Page/PLugins.vue
  @description This component is the plugin page.
  This page displays global information about plugins, and allow to delete or upload some plugins.
*/

const plugins = reactive({
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
  plugins.builder = data;
});

onMounted(() => {
  useGlobal();
});

const builder = [
  {
    type: "card",
    containerColumns: { pc: 12, tablet: 12, mobile: 12 },
    widgets: [
      {
        type: "Title",
        data: {
          title: "dashboard_plugins",
          type: "card",
        },
      },
      {
        type: "PluginBox",
        data: {
          name: "Plugin name",
          columns: { pc: 4, tablet: 6, mobile: 12 },
          popovers: [
            {
              text: "External plugin",
              iconName: "external",
              iconColor: "info",
            },
          ],
        },
      },
      {
        type: "PluginBox",
        data: {
          name: "Plugin name",
          columns: { pc: 4, tablet: 6, mobile: 12 },
          popovers: [
            {
              text: "Pro plugin",
              iconName: "crown",
              iconColor: "amber",
            },
          ],
        },
      },
      {
        type: "PluginBox",
        data: {
          name: "Plugin name",
          columns: { pc: 4, tablet: 6, mobile: 12 },
          popovers: [
            {
              text: "Core plugin",
              iconName: "core",
              iconColor: "red",
            },
          ],
        },
      },
    ],
  },
];
</script>

<template>
  <DashboardLayout>
    <BuilderPlugins v-if="builder" :builder="builder" />
  </DashboardLayout>
</template>
