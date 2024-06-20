<script setup>
import { reactive, onBeforeMount } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderPlugins from "@components/Builder/Plugins.vue";

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
        type: "ListDetails",
        data: {
          filters: [
            {
              filter: "details",
              filterName: "keyword",
              type: "keyword",
              value: "",
              keys: ["text"],
              field: {
                id: `filter-plugin-name`,
                value: "",
                type: "text",
                name: `filter-plugin-name`,
                containerClass: "setting",
                label: "plugins_search",
                placeholder: "inp_keyword",
                isClipboard: false,
                popovers: [
                  {
                    text: "plugins_search_desc",
                    iconName: "info",
                    iconColor: "info",
                    svgSize: "sm",
                  },
                ],
                columns: { pc: 3, tablet: 4, mobile: 12 },
              },
            },
            {
              filter: "details",
              filterName: "type",
              type: "select",
              value: "all",
              keys: ["type"],
              field: {
                id: `filter-plugin-type`,
                value: "all",
                values: ["all", "pro", "core", "external"],
                name: `filter-plugin-type`,
                onlyDown: true,
                label: "plugins_type",
                containerClass: "setting",
                maxBtnChars: 24,
                popovers: [
                  {
                    text: "plugins_type_desc",
                    iconName: "info",
                    iconColor: "info",
                    svgSize: "sm",
                  },
                ],
                columns: { pc: 3, tablet: 4, mobile: 12 },
              },
            },
          ],
          columns: { pc: 4, tablet: 6, mobile: 12 },
          details: [
            {
              text: "Pro",
              type: "pro",
              disabled: true,
              popovers: [
                {
                  text: "plugins_pro_plugin",
                  iconName: "crown",
                  iconColor: "amber",
                },
              ],
            },
            {
              text: "Core",
              type: "core",
              popovers: [
                {
                  text: "plugins_core_plugin",
                  iconName: "core",
                  iconColor: "red",
                },
              ],
            },
            {
              text: "external",
              type: "external",
              popovers: [
                {
                  text: "plugins_redirect_page",
                  iconName: "redirect",
                  iconColor: "info",
                },
                {
                  text: "plugins_external_plugin",
                  iconName: "external",
                  iconColor: "blue",
                },
              ],
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
