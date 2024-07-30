<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderPlugins from "@components/Builder/Plugins.vue";
import { useForm } from "@utils/form.js";

/**
  @name Page/PLugins.vue
  @description This component is the plugin page.
  This page displays global information about plugins, and allow to delete or upload some plugins.
*/

const plugins = reactive({
  builder: "",
});

// Case we click on redirect icon, go to the redirect plugin page
function redirectPlugin() {
  window.addEventListener(
    "click",
    (e) => {
      // Case avoid redirect
      if (e.target.tagName !== "A") return;
      if (!e.target.closest("[data-plugin-redirect]")) return;
      if (
        e.target
          .closest("[data-plugin-redirect]")
          ?.getAttribute("data-plugin-redirect") !== "true" ||
        !e.target.querySelector('[data-svg="redirect"]')
      )
        return;
      // Prepare redirect
      const pluginId = e.target
        .closest("[data-plugin-id]")
        .getAttribute("data-plugin-id");

      window.location.href = `./${pluginId}`;
    },
    true
  );
}

// Case we click on redirect icon, go to the redirect plugin page
function deletePlugin() {
  const deleteData = {
    name: "pluginName",
    id: "pluginId",
    type: "pluginType",
    operation: "delete",
  };
  window.addEventListener(
    "click",
    (e) => {
      // Case avoid redirect
      if (e.target.tagName !== "A") return;
      if (!e.target.closest("[data-plugin-delete]")) return;
      if (
        e.target
          .closest("[data-plugin-delete]")
          .getAttribute("data-plugin-delete") !== "true" ||
        !e.target.querySelector('[data-svg="trash"]')
      )
        return;
      // Update data
      deleteData.name = e.target
        .closest("[data-plugin-name]")
        .getAttribute("data-plugin-name");
      deleteData.id = e.target
        .closest("[data-plugin-id]")
        .getAttribute("data-plugin-id");
      deleteData.type = e.target
        .closest("[data-plugin-type]")
        .getAttribute("data-plugin-type");
      // Attach data to submit button (need to check attributs data-delete-plugin-submit)
      const submitBtn = document.querySelector("[data-delete-plugin-submit]");
      submitBtn.setAttribute("data-submit-form", JSON.stringify(deleteData));

      // Prepare and show modal
      const modal = document.querySelector("#modal-delete-plugin");
      const modalPluginName = modal.querySelector("[data-modal-plugin-name]");
      modalPluginName.textContent = deleteData.name;
      modal.classList.remove("hidden");
    },
    true
  );
}

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
  redirectPlugin();
  deletePlugin();
});

const builder = [
  {
    type: "modal",
    id: "modal-delete-plugin",
    widgets: [
      {
        type: "Title",
        data: {
          title: "plugins_modal_delete_title",
          type: "modal",
        },
      },
      {
        type: "Text",
        data: {
          text: "plugins_modal_delete_confirm",
        },
      },
      {
        type: "Text",
        data: {
          text: "",
          bold: true,
          attrs: {
            "data-modal-plugin-name": "true",
          },
        },
      },
      {
        type: "ButtonGroup",
        data: {
          buttons: [
            {
              id: "delete-plugin-btn",
              text: "action_close",
              disabled: false,
              color: "close",
              size: "normal",
              attrs: {
                "data-hide-el": "modal-delete-plugin",
              },
            },
            {
              id: "delete-plugin-btn",
              text: "action_delete",
              disabled: false,
              color: "delete",
              size: "normal",
              attrs: {
                "data-delete-plugin-submit": "",
              },
            },
          ],
          groupClass: "btn-group-modal",
        },
      },
    ],
  },
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
                label: "plugins_search",
                placeholder: "inp_keyword",
                isClipboard: false,
                popovers: [
                  {
                    text: "plugins_search_desc",
                    iconName: "info",
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
                maxBtnChars: 24,
                popovers: [
                  {
                    text: "plugins_type_desc",
                    iconName: "info",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "pro",
                "data-plugin-name": "General",
              },
              disabled: true,
              popovers: [
                {
                  text: "plugins_pro_plugin_desc",
                  iconName: "crown",
                },
              ],
            },
            {
              text: "Antibot",
              type: "core",
              attrs: {
                "data-plugin-id": "antibot",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Antibot",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Auth basic",
              type: "core",
              attrs: {
                "data-plugin-id": "authbasic",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Auth basic",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "pro",
                "data-plugin-name": "Backup",
              },
              disabled: true,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
                {
                  text: "plugins_pro_plugin_desc",
                  iconName: "crown",
                },
              ],
            },
            {
              text: "Bad behavior",
              type: "external",
              attrs: {
                "data-plugin-id": "badbehavior",
                "data-plugin-delete": "true",
                "data-plugin-redirect": "true",
                "data-plugin-type": "external",
                "data-plugin-name": "Bad behavior",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
                {
                  text: "plugins_delete_desc",
                  iconName: "trash",
                },
              ],
            },
            {
              text: "Blacklist",
              type: "core",
              attrs: {
                "data-plugin-id": "blacklist",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Blacklist",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Brotli",
              type: "core",
              attrs: {
                "data-plugin-id": "brotli",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Brotli",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "BunkerNet",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "CORS",
              type: "core",
              attrs: {
                "data-plugin-id": "cors",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "CORS",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Client cache",
              type: "core",
              attrs: {
                "data-plugin-id": "clientcache",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Client cache",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Country",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Custom HTTPS certificate",
              type: "core",
              attrs: {
                "data-plugin-id": "customcert",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Custom HTTPS certificate",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "DB",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "DNSBL",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Errors",
              type: "core",
              attrs: {
                "data-plugin-id": "errors",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Errors",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Greylist",
              type: "core",
              attrs: {
                "data-plugin-id": "greylist",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Greylist",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Gzip",
              type: "core",
              attrs: {
                "data-plugin-id": "gzip",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Gzip",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "HTML injection",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Headers",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Jobs",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Let's Encrypt",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Limit",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Metrics",
              type: "core",
              attrs: {
                "data-plugin-id": "metrics",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Metrics",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Miscellaneous",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "ModSecurity",
              type: "core",
              attrs: {
                "data-plugin-id": "modsecurity",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "ModSecurity",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "PHP",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Pro",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Real IP",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Redirect",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Redis",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Reverse proxy",
              type: "core",
              attrs: {
                "data-plugin-id": "reverseproxy",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Reverse proxy",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Reverse scan",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
                },
              ],
            },
            {
              text: "Self-signed certificate",
              type: "core",
              attrs: {
                "data-plugin-id": "selfsigned",
                "data-plugin-delete": "false",
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Self-signed certificate",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "Sessions",
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
                "data-plugin-redirect": "false",
                "data-plugin-type": "core",
                "data-plugin-name": "UI",
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
                "data-plugin-redirect": "true",
                "data-plugin-type": "core",
                "data-plugin-name": "Whitelist",
              },
              disabled: false,
              popovers: [
                {
                  text: "plugins_redirect_page_desc",
                  iconName: "redirect",
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
