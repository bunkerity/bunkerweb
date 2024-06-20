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
              filter: "default",
              filterName: "keyword",
              type: "keyword",
              value: "",
              keys: ["text"],
              field: {
                id: "filter-plugin-name",
                value: "",
                type: "text",
                name: "filter-plugin-name",
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
                columns: {
                  pc: 3,
                  tablet: 4,
                  mobile: 12,
                },
              },
            },
            {
              filter: "default",
              filterName: "type",
              type: "select",
              value: "all",
              keys: ["type"],
              field: {
                id: "filter-plugin-type",
                value: "all",
                values: ["all", "pro", "core", "external"],
                name: "filter-plugin-type",
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
                columns: {
                  pc: 3,
                  tablet: 4,
                  mobile: 12,
                },
              },
            },
          ],
          details: [
            {
              text: "General",
              type: "pro",
              attrs: {
                "data-plugin-id": "general",
                "data-plugin-delete": "false",
              },
              disabled: true,
              popovers: [
                {
                  text: "plugins_pro_plugin_desc",
                  iconName: "crown",
                  iconColor: "amber",
                },
              ],
            },
            {
              text: "Antibot",
              type: "core",
              attrs: {
                "data-plugin-id": "antibot",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Auth basic",
              type: "core",
              attrs: {
                "data-plugin-id": "authbasic",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Backup",
              type: "pro",
              attrs: {
                "data-plugin-id": "backup",
                "data-plugin-delete": "false",
              },
              disabled: true,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
                {
                  text: "plugins_pro_plugin_desc",
                  iconName: "crown",
                  iconColor: "amber",
                },
              ],
            },
            {
              text: "Bad behavior",
              type: "external",
              attrs: {
                "data-plugin-id": "badbehavior",
                "data-plugin-delete": "true",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
                {
                  text: "plugins_delete_desc",
                  iconName: "trash",
                  iconColor: "red",
                },
              ],
            },
            {
              text: "Blacklist",
              type: "core",
              attrs: {
                "data-plugin-id": "blacklist",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Brotli",
              type: "core",
              attrs: {
                "data-plugin-id": "brotli",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "BunkerNet",
              type: "core",
              attrs: {
                "data-plugin-id": "bunkernet",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "CORS",
              type: "core",
              attrs: {
                "data-plugin-id": "cors",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Client cache",
              type: "core",
              attrs: {
                "data-plugin-id": "clientcache",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Country",
              type: "core",
              attrs: {
                "data-plugin-id": "country",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Custom HTTPS certificate",
              type: "core",
              attrs: {
                "data-plugin-id": "customcert",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "DB",
              type: "core",
              attrs: {
                "data-plugin-id": "db",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "DNSBL",
              type: "core",
              attrs: {
                "data-plugin-id": "dnsbl",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Errors",
              type: "core",
              attrs: {
                "data-plugin-id": "errors",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Greylist",
              type: "core",
              attrs: {
                "data-plugin-id": "greylist",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Gzip",
              type: "core",
              attrs: {
                "data-plugin-id": "gzip",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "HTML injection",
              type: "core",
              attrs: {
                "data-plugin-id": "inject",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Headers",
              type: "core",
              attrs: {
                "data-plugin-id": "headers",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Jobs",
              type: "core",
              attrs: {
                "data-plugin-id": "jobs",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Let's Encrypt",
              type: "core",
              attrs: {
                "data-plugin-id": "letsencrypt",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Limit",
              type: "core",
              attrs: {
                "data-plugin-id": "limit",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Metrics",
              type: "core",
              attrs: {
                "data-plugin-id": "metrics",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Miscellaneous",
              type: "core",
              attrs: {
                "data-plugin-id": "misc",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "ModSecurity",
              type: "core",
              attrs: {
                "data-plugin-id": "modsecurity",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "PHP",
              type: "core",
              attrs: {
                "data-plugin-id": "php",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Pro",
              type: "core",
              attrs: {
                "data-plugin-id": "pro",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Real IP",
              type: "core",
              attrs: {
                "data-plugin-id": "realip",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Redirect",
              type: "core",
              attrs: {
                "data-plugin-id": "redirect",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Redis",
              type: "core",
              attrs: {
                "data-plugin-id": "redis",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Reverse proxy",
              type: "core",
              attrs: {
                "data-plugin-id": "reverseproxy",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Reverse scan",
              type: "core",
              attrs: {
                "data-plugin-id": "reversescan",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
            {
              text: "Self-signed certificate",
              type: "core",
              attrs: {
                "data-plugin-id": "selfsigned",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Sessions",
              type: "core",
              attrs: {
                "data-plugin-id": "sessions",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "UI",
              type: "core",
              attrs: {
                "data-plugin-id": "ui",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [],
            },
            {
              text: "Whitelist",
              type: "core",
              attrs: {
                "data-plugin-id": "whitelist",
                "data-plugin-delete": "false",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                  iconColor: "blue",
                },
              ],
            },
          ],
          columns: {
            pc: 4,
            tablet: 6,
            mobile: 12,
          },
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
