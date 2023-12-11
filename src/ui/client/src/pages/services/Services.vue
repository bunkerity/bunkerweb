<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import ButtonBase from "@components/Button/Base.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import CardLabel from "@components/Card/Label.vue";
import PluginStructure from "@components/Plugin/Structure.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import SettingsUploadSvgWarning from "@components/Settings/Upload/Svg/Warning.vue";
import ServicesModalDelete from "@components/Services/Modal/Delete.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { getMethodList, getSettingsByFilter } from "@utils/settings.js";
import {
  setPluginsData,
  addConfToPlugins,
  getPluginsByContext,
  pluginI18n,
  getRemainFromFilter,
} from "@utils/plugins.js";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useConfigStore } from "@store/settings.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";
import { useI18n } from "vue-i18n";
const { locale, fallbackLocale } = useI18n();

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  refresh();
});

const logsStore = useLogsStore();
logsStore.setTags(["plugin", "config"]);

const config = useConfigStore();

// Disabled save when no SERVER_NAME value
watch(config, () => {
  if (!services.activeService) return (saveBtn.disabled = true);
  // Case active service has no setting, he is not store on config even if he is active
  const isServ = !!(services.activeService in config.data.services);
  if (!isServ) return (saveBtn.disabled = true);
  const isNewName = !!(
    "SERVER_NAME" in config.data.services[services.activeService]
  );

  // Check if can save regarding name logic
  // new service must have SERVER_NAME
  if (services.activeService === "new" && !isNewName)
    return (saveBtn.disabled = true);

  // When a SERVER_NAME is set, it must be unique (not taken, not falsy)
  if (isNewName) {
    if (
      !config.data.services[services.activeService]["SERVER_NAME"] ||
      (config.data.services[services.activeService]["SERVER_NAME"] &&
        services.servicesName.includes(
          config.data.services[services.activeService]["SERVER_NAME"]
        ))
    ) {
      return (saveBtn.disabled = true);
    }
  }

  // Case not new service
  // We can save if at least one value is different from default
  if (
    (services.activeService !== "new" &&
      Object.keys(config.data.services).length === 0) ||
    (Object.keys(config.data.services).length > 0 &&
      Object.keys(config.data.services[services.activeService]).length === 0)
  ) {
    return (saveBtn.disabled = true);
  }

  return (saveBtn.disabled = false);
});

const feedbackStore = useFeedbackStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  keyword: "",
  method: "all",
});

// Disabled in case we are creating a new service (empty SERVER_NAME)
const saveBtn = reactive({
  disabled: false,
});

// Plugins data to render components
const services = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  // Default plugin to display, first of list (before any filter)
  activePlugin: "",
  activeService: "",
  pluginsName: [],
  servicesName: [],
  activePlugins: [],
  canDelete: computed(() => {
    // Determine if we can delete current service
    if (!services.activeService || services.activeService === "new")
      return false;

    let canDel = false;

    services.setup[services.activeService].forEach((plugin) => {
      if (plugin.id.toLowerCase() !== "general") return;

      for (const [key, value] of Object.entries(plugin.settings)) {
        if (key.toUpperCase() !== "SERVER_NAME") continue;
        const method = value["method"];
        if (method === "default" || method === "ui") canDel = true;
        break;
      }
    });
    return canDel;
  }),
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    if (
      services.isErr ||
      services.isPend ||
      !services.data ||
      services.data.length === 0 ||
      conf.isErr ||
      conf.isPend ||
      !conf.data ||
      conf.data.length === 0
    ) {
      return [];
    }

    // Get format multisite data
    const cloneMultisitePlugin = setPluginsData(
      getPluginsByContext(
        JSON.parse(JSON.stringify(services.data)),
        "multisite"
      )
    );

    // translate
    pluginI18n(cloneMultisitePlugin, locale.value, fallbackLocale.value);

    // Get only services custom conf
    const cloneServConf = JSON.parse(JSON.stringify(conf.data["services"]));

    // For each service, get all multisite plugins and add custom service conf
    // Merge everything on related service
    services.servicesName = [];
    for (const [key, value] of Object.entries(cloneServConf)) {
      services.servicesName.push(key);
      const currServPlugin = JSON.parse(JSON.stringify(cloneMultisitePlugin));
      const currServConf = cloneServConf[key];
      // Add current name
      if (!("SERVER_NAME" in currServConf)) {
        currServConf["SERVER_NAME"] = {
          value: key,
          method: "default",
        };
      }

      cloneServConf[key] = addConfToPlugins(currServPlugin, currServConf);
    }

    // Add new service with all default values
    // Will not be add to config store until a default value is change
    // services.setup is at least length 1
    cloneServConf["new"] = JSON.parse(JSON.stringify(cloneMultisitePlugin));
    // New default server_name should be empty
    cloneServConf["new"].forEach((plugin) => {
      if (plugin.id.toLowerCase() !== "general") return;

      for (const [key, value] of Object.entries(plugin.settings)) {
        if (key.toUpperCase() !== "SERVER_NAME") continue;
        value["default"] = "";
      }
    });
    for (const [key, value] of Object.entries(cloneServConf)) {
      cloneServConf[key] = getSettingsByFilter(cloneServConf[key], filters);
    }

    // Filter data to display for each service
    for (const [key, value] of Object.entries(cloneServConf)) {
      cloneServConf[key] = getSettingsByFilter(cloneServConf[key], filters);
    }

    // Set first service as active if none
    if (!services.activeService)
      services.activeService = services.servicesName[0] || "";
    // Get remain plugin after filter
    // Use new service because always here
    services.activePlugins = getRemainFromFilter(cloneServConf["new"]);

    // Set first plugin as active if none
    if (!services.activePlugin)
      services.activePlugin =
        services.activePlugins.length > 0 ? services.activePlugins[0] : "";

    // Case active plugin before update, need some check
    if (services.activePlugin) {
      // Case prev active plugin passed filter
      const isPlugin =
        services.activePlugins.indexOf(services.activePlugin) !== -1
          ? true
          : false;

      // Case not, set first passed one or empty
      if (!isPlugin) {
        services.activePlugin =
          services.activePlugins.length > 0 ? services.activePlugins[0] : "";
      }
    }
    return cloneServConf;
  }),
});

const conf = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
});

async function getGlobalConf(isFeedback = true) {
  // Remove previous config services changes
  resetValues();
  conf.isPend = true;
  services.isPend = true;
  await fetchAPI(
    "/api/config?methods=1&new_format=1",
    "GET",
    null,
    conf,
    isFeedback ? feedbackStore.addFeedback : null
  );
  await fetchAPI(
    "/api/plugins",
    "GET",
    null,
    services,
    isFeedback ? feedbackStore.addFeedback : null
  );
}

// Refetch and reset all states
function resetValues() {
  services.activeService = "";
  services.activePlugin = "";
  filters.label = "";
  config.$reset();
}

function refresh() {
  resetValues();
  getGlobalConf();
}

async function sendServConf() {
  // Case nothing to send
  if (Object.keys(config.data.services).length === 0) return;

  const promises = [];
  // Send services
  const services = config.data.services;
  if (Object.keys(services).length > 0) {
    for (const [key, value] of Object.entries(services)) {
      if (Object.keys(value).length === 0) continue;
      let serviceName;
      // Case new, replace by SERVER_NAME
      if (key !== "new") serviceName = key;
      // Case change existing service name
      try {
        serviceName = services[key]["SERVER_NAME"];
      } catch (err) {}
      promises.push(
        await fetchAPI(
          `/api/config/service/${serviceName}?method=ui`,
          "PUT",
          services[key],
          null,
          feedbackStore.addFeedback
        )
      );
    }

    // When all conf responded, refetch global conf
    Promise.all(promises).then((services) => {
      getGlobalConf(false);
    });
  }
}

function changeServ(servName) {
  // Case current service, stop
  if (services.activeService === servName) return;
  // Else setup
  // Remove previous config services changes
  resetValues();
  services.activeService = servName;
}

const delModal = reactive({
  isOpen: false,
});

// Show service data logic
onMounted(() => {
  getGlobalConf();
});
</script>

<template>
  <Dashboard>
    <ServicesModalDelete
      :serviceName="services.activeService"
      :isOpen="delModal.isOpen"
      @close="delModal.isOpen = false"
      @delete="refresh()"
    />
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="conf.isErr || services.isErr"
      :isPend="conf.isPend || services.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_services') }),
        isErr: $t('api_error', { name: $t('dashboard_services') }),
      }"
    />
    <div
      v-if="!services.isErr && !services.isPend"
      class="col-span-12 content-wrap"
    >
      <div class="col-span-12 flex justify-center mt-2">
        <ButtonBase
          @click="changeServ('new')"
          color="valid"
          size="normal"
          class="text-sm"
        >
          {{ $t("services_actions_new") }}
        </ButtonBase>
      </div>
      <CardBase
        class="z-[102] h-fit col-span-12 md:col-span-4 lg:col-span-3 3xl:col-span-2"
        :label="$t('dashboard_info')"
      >
        <CardItemList
          :items="[
            {
              label: $t('services_total'),
              value: Object.keys(services.setup).length - 1,
            },
            {
              label: $t('dashboard_scheduler'),
              value: '',
            },
            {
              label: $t('dashboard_ui'),
              value: '',
            },
          ]"
        />
      </CardBase>
      <CardBase
        class="z-[101] h-fit col-span-12 md:col-span-8 lg:col-span-5 3xl:col-span-3"
      >
        <CardLabel :label="$t('services_list_title')" />
        <SettingsLayout
          v-if="Object.keys(services.setup).length > 1"
          class="flex w-full col-span-12"
          :label="$t('services_list_select_service')"
          name="services-list"
        >
          <SettingsSelect
            @inp="(v) => changeServ(v)"
            :settings="{
              id: 'services-list',
              value:
                services.activeService === 'new' ? '' : services.activeService,
              values: Object.keys(services.setup).filter(
                (item) => item !== 'new'
              ),
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12"
          :label="$t('services_list_select_plugin')"
          name="plugins"
        >
          <SettingsSelect
            @inp="(v) => (services.activePlugin = v)"
            :settings="{
              id: 'plugins',
              value: services.activePlugin,
              values: services.activePlugins,
            }"
          />
        </SettingsLayout>
        <div class="col-span-12 flex flex-col justify-center items-center mt-2">
          <hr class="line-separator z-10 w-full" />
          <p class="dark:text-gray-500 text-xs text-center mt-1 mb-2">
            <span class="mx-0.5">
              <SettingsUploadSvgWarning class="scale-90" />
            </span>
            {{ $t("services_list_switch_warning") }}
          </p>
        </div>
      </CardBase>
      <CardBase
        :label="$t('dashboard_filter')"
        class="z-[100] h-fit col-span-12 lg:col-span-4 grid grid-cols-12 relative"
      >
        <SettingsLayout
          class="flex w-full col-span-12 md:col-span-6 lg:col-span-12"
          :label="$t('services_filter_search_setting')"
          name="keyword"
        >
          <SettingsInput
            @inp="(v) => (filters.keyword = v)"
            :settings="{
              id: 'keyword',
              type: 'text',
              value: '',
              placeholder: $t('services_filter_search_setting_placeholder'),
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12 md:col-span-6 lg:col-span-12"
          :label="$t('services_filter_method_setting')"
          name="method"
        >
          <SettingsSelect
            @inp="(v) => (filters.method = v)"
            :settings="{
              id: 'method',
              value: filters.method,
              values: getMethodList(),
            }"
          />
        </SettingsLayout>
      </CardBase>

      <CardBase
        v-if="services.activeService"
        class="z-10 col-span-12 grid grid-cols-12 relative"
      >
        <div class="col-span-12 flex items-center">
          <button
            v-if="services.canDelete"
            @click="delModal.isOpen = true"
            color="delete"
            class="rounded-full bg-red-500 w-8 h-8 mr-1 mb-2 hover:brightness-90 dark:hover:brightness-75 dark:brightness-90"
          >
            <span class="sr-only">{{ `${$t("services_active_delete")}` }}</span>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke-width="1.5"
              stroke="currentColor"
              class="pointer-events-none w-5 h-5 stroke-white"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
              />
            </svg>
          </button>
          <CardLabel
            class="w-full text-xl mb-0"
            :label="
              services.activeService === 'new'
                ? $t('services_active_new')
                : $t('services_active_base', {
                    name: services.activeService,
                  })
            "
          />
        </div>
        <hr class="col-span-12 line-separator z-10 w-full mb-6" />

        <div class="col-span-12" v-for="(value, key) in services.setup">
          <PluginStructure
            v-if="services.activeService === key"
            :serviceName="key"
            :plugins="value"
            :active="services.activePlugin"
          />
        </div>
        <div
          class="col-span-12 flex flex-col items-center w-full justify-center mt-8 mb-2"
        >
          <ButtonBase
            :disabled="saveBtn.disabled"
            @click="sendServConf()"
            color="valid"
            size="lg"
            class="w-fit"
          >
            {{ $t("action_save") }}
          </ButtonBase>
          <hr class="line-separator z-10 w-1/2" />
          <p class="dark:text-gray-500 text-xs text-center mt-1 mb-2">
            <span class="mx-0.5">
              <SettingsUploadSvgWarning class="scale-90" />
            </span>
            {{ $t("services_actions_warning") }}
          </p>
        </div>
      </CardBase>
    </div>
  </Dashboard>
</template>
