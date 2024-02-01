<script setup>
import { reactive, computed, onMounted, watch } from "vue";
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import ServicesButtonAdd from "@components/Services/Button/Add.vue";
import ServicesButtonFilter from "@components/Services/Button/Filter.vue";
import CardBase from "@components/Card/Base.vue";
import CardLabel from "@components/Card/Label.vue";
import CardItemList from "@components/Card/Item/List.vue";
import ServicesModalDelete from "@components/Services/Modal/Delete.vue";
import ServicesCard from "@components/Services/Card.vue";
import ServicesModalSettings from "@components/Services/Modal/Settings.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { getServicesByFilter, getServicesMethods } from "@utils/services.js";
import {
  setPluginsData,
  addConfToPlugins,
  getPluginsByContext,
  pluginI18n,
} from "@utils/plugins.js";
import { fetchAPI } from "@utils/api.js";
import { contentIndex } from "@utils/tabindex.js";
import {
  useModalStore,
  useDelModalStore,
  useFilterStore,
} from "@store/services.js";
import { useFeedbackStore, useRefreshStore } from "@store/global.js";
import { useConfigStore } from "@store/settings.js";
import { useLogsStore } from "@store/logs.js";
import { useI18n } from "vue-i18n";

const { locale, fallbackLocale } = useI18n();

const filterStore = useFilterStore();
const modalStore = useModalStore();
const delModalStore = useDelModalStore();
const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();
const config = useConfigStore();

watch(refreshStore, () => {
  config.$reset();
  filters.servName = "";
  filters.servMethod = "all";
  services.methods = [];
  services.filters = {};
  getGlobalConf(false);
});

watch(filterStore, () => {
  if (!filterStore.isOpen) {
    filters.badbehavior = "all";
    filters.limit = "all";
    filters.reverseproxy = "all";
    filters.modsecurity = "all";
    filters.cors = "all";
    filters.dnsbl = "all";
  }
});

const logsStore = useLogsStore();
logsStore.setTags(["plugin", "config"]);

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  servName: "",
  servMethod: "all",
  isDraft: "all",
  // equal to details items
  badbehavior: "all",
  limit: "all",
  reverseproxy: "all",
  modsecurity: "all",
  cors: "all",
  dnsbl: "all",
});

// Show some details on card, without opening settings modal
// lang : id for i18n
// setting : setting name on plugin
// id : id for plugin
const details = [
  {
    lang: "bad_behavior",
    id: "badbehavior",
    setting: "USE_BAD_BEHAVIOR",
  },
  {
    lang: "modsecurity",
    id: "modsecurity",
    setting: "USE_MODSECURITY",
  },
  {
    lang: "limit",
    id: "limit",
    setting: "USE_LIMIT_REQ",
  },
  {
    lang: "reverse_proxy",
    id: "reverseproxy",
    setting: "USE_REVERSE_PROXY",
  },
  {
    lang: "cors",
    id: "cors",
    setting: "USE_CORS",
  },
  {
    lang: "dnsbl",
    id: "dnsbl",
    setting: "USE_DNSBL",
  },
];

// Plugins data to render components
const services = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  filters: {},
  methods: [],
  methodsCount: 0,
  servicesCount: 0,
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

    // Get all services names
    modalStore.data.servicesName = Object.keys(cloneServConf);
    services.servicesCount = Object.keys(cloneServConf).length;

    // Get methods only on page rendering or refresh services data
    if (services.methods.length === 0)
      services.methods = ["all"].concat(getServicesMethods(cloneServConf));
    services.methodsCount = getServicesMethods(cloneServConf).length;

    // Add filtering
    services.filters = getServicesByFilter(cloneServConf, filters, details);

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

function setModal(modal, operation, serviceName, service) {
  modal.data.operation = operation;
  modal.data.service = service;
  modal.data.serviceName = serviceName;
  modal.isOpen = true;
}

// Show service data logic
onMounted(() => {
  getGlobalConf();
});
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

    <div
      v-if="!services.isErr && !services.isPend"
      class="col-span-12 content-wrap"
    >
      <div
        class="col-span-12 relative flex justify-center min-w-0 break-words rounded-2xl bg-clip-border"
      >
        <ServicesButtonAdd
          :tabindex="
            modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
          "
          v-if="!services.isErr && !services.isPend"
          @click="setModal(modalStore, 'create', 'new', services.new)"
        />
      </div>

      <CardBase
        class="h-fit col-span-12 md:col-span-4 lg:col-span-3"
        :label="$t('dashboard_info')"
      >
        <CardItemList
          :items="[
            {
              label: $t('services_total'),
              value: services.servicesCount,
            },
            {
              label: $t('services_methods_count'),
              value: services.methodsCount,
            },
          ]"
        />
      </CardBase>
      <CardBase
        class="z-10 h-fit col-span-12 md:col-span-8 lg:col-span-6 2xl:col-span-5"
      >
        <div class="col-span-12 flex justify-start items-start">
          <CardLabel :label="$t('dashboard_filter')" />
          <ServicesButtonFilter
            :tabindex="
              modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
            "
          />
        </div>
        <SettingsLayout
          class="flex w-full col-span-12 sm:col-span-6"
          :label="$t('services_service_search')"
        >
          <SettingsInput
            @inp="(v) => (filters.servName = v)"
            :tabId="
              modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
            "
            :settings="{
              id: 'servName',
              type: 'text',
              value: '',
              placeholder: $t('services_service_search_placeholder'),
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12 sm:col-span-6"
          :label="$t('services_service_select_method')"
        >
          <SettingsSelect
            @inp="(v) => (filters.servMethod = v)"
            :tabId="
              modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
            "
            :settings="{
              id: 'servMethods',
              value: 'all',
              values: services.methods,
            }"
            :key="services.methods"
          />
        </SettingsLayout>
        <div
          :class="[filterStore.isOpen ? '' : 'hidden']"
          class="col-span-12 grid grid-cols-12"
          id="service-card-filter-more"
          :aria-hidden="filterStore.isOpen ? 'true' : 'false'"
        >
          <div class="col-span-12">
            <h3
              class="mx-2 my-2 text-base uppercase font-bold dark:text-white/90 mb-0"
            >
              {{ $t("dashboard_advanced") }}
            </h3>
          </div>

          <SettingsLayout
            :key="filterStore.isOpen"
            class="flex w-full col-span-12 sm:col-span-6"
            :label="$t('services_service_select_bad_behavior')"
          >
            <SettingsSelect
              @inp="(v) => (filters.badbehavior = v)"
              :tabId="
                modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
              "
              :settings="{
                id: 'bad-behavior-filter',
                value: 'all',
                values: ['all', 'true', 'false'],
              }"
            />
          </SettingsLayout>
          <SettingsLayout
            :key="filterStore.isOpen"
            class="flex w-full col-span-12 sm:col-span-6"
            :label="$t('services_service_select_limit')"
          >
            <SettingsSelect
              @inp="(v) => (filters.limit = v)"
              :tabId="
                modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
              "
              :settings="{
                id: 'limit-filter',
                value: 'all',
                values: ['all', 'true', 'false'],
              }"
            />
          </SettingsLayout>
          <SettingsLayout
            :key="filterStore.isOpen"
            class="flex w-full col-span-12 sm:col-span-6"
            :label="$t('services_service_select_reverse_proxy')"
          >
            <SettingsSelect
              @inp="(v) => (filters.reverseproxy = v)"
              :tabId="
                modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
              "
              :settings="{
                id: 'reverse-proxy-filter',
                value: 'all',
                values: ['all', 'true', 'false'],
              }"
            />
          </SettingsLayout>
          <SettingsLayout
            :key="filterStore.isOpen"
            class="flex w-full col-span-12 sm:col-span-6"
            :label="$t('services_service_select_modsecurity')"
          >
            <SettingsSelect
              @inp="(v) => (filters.modsecurity = v)"
              :tabId="
                modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
              "
              :settings="{
                id: 'modsecurity-filter',
                value: 'all',
                values: ['all', 'true', 'false'],
              }"
            />
          </SettingsLayout>
          <SettingsLayout
            :key="filterStore.isOpen"
            class="flex w-full col-span-12 sm:col-span-6"
            :label="$t('services_service_select_cors')"
          >
            <SettingsSelect
              @inp="(v) => (filters.cors = v)"
              :tabId="
                modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
              "
              :settings="{
                id: 'cors-filter',
                value: 'all',
                values: ['all', 'true', 'false'],
              }"
            />
          </SettingsLayout>
          <SettingsLayout
            :key="filterStore.isOpen"
            class="flex w-full col-span-12 sm:col-span-6"
            :label="$t('services_service_select_dnsbl')"
          >
            <SettingsSelect
              @inp="(v) => (filters.dnsbl = v)"
              :tabId="
                modalStore.isOpen || delModalStore.isOpen ? -1 : contentIndex
              "
              :settings="{
                id: 'dnsbl-filter',
                value: 'all',
                values: ['all', 'true', 'false'],
              }"
            />
          </SettingsLayout>
        </div>
      </CardBase>
    </div>

    <ServicesModalSettings v-if="!services.isErr && !services.isPend" />
    <ServicesModalDelete v-if="!services.isErr && !services.isPend" />

    <div
      v-if="!services.isErr && !services.isPend"
      class="col-span-12 content-wrap"
    >
      <ServicesCard
        v-if="!services.isErr && !services.isPend && services.services"
        :services="services.services"
        :filters="services.filters"
        :details="details"
      />
    </div>
  </Dashboard>
</template>
