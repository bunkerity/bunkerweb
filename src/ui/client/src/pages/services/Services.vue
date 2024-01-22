<script setup>
import { reactive, computed, onMounted, watch } from "vue";
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import ServicesButtonAdd from "@components/Services/Button/Add.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import ServicesModalDelete from "@components/Services/Modal/Delete.vue";
import ServicesCard from "@components/Services/Card.vue";
import ServicesModalSettings from "@components/Services/Modal/Settings.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { getMethodList } from "@utils/settings.js";
import {
  setPluginsData,
  addConfToPlugins,
  getPluginsByContext,
  pluginI18n,
} from "@utils/plugins.js";
import { fetchAPI } from "@utils/api.js";
import { contentIndex } from "@utils/tabindex.js";
import { useModalStore } from "@store/services.js";
import { useFeedbackStore, useRefreshStore } from "@store/global.js";
import { useConfigStore } from "@store/settings.js";
import { useLogsStore } from "@store/logs.js";
import { useI18n } from "vue-i18n";

const { locale, fallbackLocale } = useI18n();

const modalStore = useModalStore();
const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();
const config = useConfigStore();

watch(refreshStore, () => {
  config.$reset();
  refresh();
});

const logsStore = useLogsStore();
logsStore.setTags(["plugin", "config"]);

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  servName: "",
  servMethod: "all",
});

// Plugins data to render components
const services = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  // Get new service
  new: computed(() => {
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
    const newServ = getI18nMultisitePlugin();

    // Add new service with all default values
    // Will not be add to config store until a default value is change
    // services.setup is at least length 1
    // New default server_name should be empty
    newServ.forEach((plugin) => {
      if (plugin.id.toLowerCase() !== "general") return;

      for (const [key, value] of Object.entries(plugin.settings)) {
        if (key.toUpperCase() !== "SERVER_NAME") continue;
        value["default"] = "";
      }
    });

    return newServ;
  }),
  // Get plugin, set current config and return
  services: computed(() => {
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
    const cloneMultisitePlugin = getI18nMultisitePlugin();

    // Get only services custom conf
    const cloneServConf = JSON.parse(JSON.stringify(conf.data["services"]));

    // For each service, get all multisite plugins and add custom service conf
    // Merge everything on related service
    for (const [key, value] of Object.entries(cloneServConf)) {
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

    return cloneServConf;
  }),
});

function getI18nMultisitePlugin() {
  // Get format multisite data
  const cloneMultisitePlugin = setPluginsData(
    getPluginsByContext(JSON.parse(JSON.stringify(services.data)), "multisite"),
  );

  // translate
  pluginI18n(cloneMultisitePlugin, locale.value, fallbackLocale.value);

  return cloneMultisitePlugin;
}

const conf = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
});

async function getGlobalConf(isFeedback = true) {
  // Remove previous config services changes
  conf.isPend = true;
  services.isPend = true;
  await fetchAPI(
    "/api/config?methods=1&new_format=1",
    "GET",
    null,
    conf,
    isFeedback ? feedbackStore.addFeedback : null,
  );
  await fetchAPI(
    "/api/plugins",
    "GET",
    null,
    services,
    isFeedback ? feedbackStore.addFeedback : null,
  );
}

// Show service data logic
onMounted(() => {
  getGlobalConf();
});

function setModal(modal, action, serviceName, service) {
  modal.data.operation = action;
  modal.data.service = service;
  // Case clone, SERVER_NAME need to be empty
  modal.data.serviceName = serviceName;
  modal.isOpen = true;
}
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="conf.isErr || services.isErr"
      :isPend="conf.isPend || services.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_services') }),
        isErr: $t('api_error', { name: $t('dashboard_services') }),
      }"
    />

    <ServicesModalDelete v-if="!services.isErr && !services.isPend" />
    <ServicesModalSettings v-if="!services.isErr && !services.isPend" />

    <div
      v-if="!services.isErr && !services.isPend"
      class="col-span-12 content-wrap"
    >
      <ServicesButtonAdd
        v-if="!services.isErr && !services.isPend"
        @click="setModal(modalStore, 'create', 'new', services.new)"
      />
      <CardBase
        class="h-fit col-span-12 md:col-span-4 lg:col-span-3 3xl:col-span-2"
        :label="$t('dashboard_info')"
      >
        <CardItemList
          :items="[
            {
              label: $t('services_total'),
              value: '',
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
        class="h-fit col-span-12 md:col-span-4 lg:col-span-3 3xl:col-span-2"
        :label="$t('dashboard_filter')"
      >
        <SettingsLayout
          class="flex w-full col-span-12 sm:col-span-6 md:col-span-4 lg:col-span-3"
          :label="$t('services_filter_search_setting')"
          name="Search service"
        >
          <SettingsInput
            @inp="(v) => (filters.servName = v)"
            :settings="{
              id: 'servName',
              type: 'text',
              value: '',
              placeholder: $t('services_filter_search_setting_placeholder'),
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12 sm:col-span-6 md:col-span-4 lg:col-span-3"
          :label="$t('services_list_select_plugin')"
          name="Methods"
        >
          <SettingsSelect
            @inp="(v) => (filters.servMethod = v)"
            :settings="{
              id: 'servMethods',
              value: 'all',
              values: getMethodList(),
            }"
          />
        </SettingsLayout>
      </CardBase>
      <ServicesCard
        v-if="!services.isErr && !services.isPend && services.services"
        :services="services.services"
      />
    </div>
  </Dashboard>
</template>
