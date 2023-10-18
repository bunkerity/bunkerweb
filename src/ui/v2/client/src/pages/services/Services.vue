<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import ButtonBase from "@components/Button/Base.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import CardLabel from "@components/Card/Label.vue";
import PluginRefresh from "@components/Plugin/Refresh.vue";
import PluginStructure from "@components/Plugin/Structure.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import SettingsUploadSvgWarning from "@components/Settings/Upload/Svg/Warning.vue";

import { reactive, computed, onMounted } from "vue";
import { getMethodList, getSettingsByFilter } from "@utils/settings.js";
import {
  setPluginsData,
  addConfToPlugins,
  getPluginsByContext,
} from "@utils/plugins.js";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useConfigStore } from "@store/settings.js";

const config = useConfigStore();
const feedbackStore = useFeedbackStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  keyword: "",
  method: "",
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
    cloneServConf["new"] = JSON.parse(JSON.stringify(cloneMultisitePlugin));

    // Filter data to display for each service
    for (const [key, value] of Object.entries(cloneServConf)) {
      cloneServConf[key] = getSettingsByFilter(cloneServConf[key], filters);
    }

    // Set first service as active if none
    if (!services.activeService)
      services.activeService = services.servicesName[0];

    // Get remain plugin after filter
    // Use active service but is impersonal (no specific service logic)
    const remainPlugins = [];
    cloneServConf[services.activeService].forEach((item) => {
      item["isMatchFilter"] ? remainPlugins.push(item.name) : false;
    });
    services.activePlugins = remainPlugins;

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

async function getGlobalConf() {
  conf.isPend = true;
  services.isPend = true;
  await fetchAPI(
    "/api/config?methods=1&new_format=1",
    "GET",
    null,
    conf,
    feedbackStore.addFeedback
  );
  await fetchAPI(
    "/api/plugins",
    "GET",
    null,
    services,
    feedbackStore.addFeedback
  );
}

// Refetch and reset all states
function resetValues() {
  filters.label = "";
  config.$reset();
}

function refresh() {
  getGlobalConf();
  resetValues();
}

function changeServ(servName) {
  services.activeService = servName;
  // Remove previous config services changes
  config.$reset();
}

async function sendServConf() {
  const promises = [];
  // Send service
  const servicesConf = conf.data.services;
  if (Object.keys(servicesConf).length > 0) {
    for (const [key, value] of Object.entries(servicesConf)) {
      if (Object.keys(value).length === 0) continue;
      const serviceName = key;
      promises.push(
        await fetchAPI(
          `/api/config/service/${serviceName}?method=ui`,
          "PUT",
          value,
          null,
          feedbackStore.addFeedback
        )
      );
    }
  }
  // When all conf responded, refetch global conf
  Promise.all(promises).then((services) => {
    getGlobalConf();
  });
}

// Show service data logic
onMounted(async () => {
  await getGlobalConf();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="services.isErr || !services.data || services.data.length === 0"
      :isPend="services.isPend"
      :textState="{
        isPend: 'Try retrieve services',
        isErr: 'Error retrieving services',
      }"
    />
    <div
      v-if="!services.isErr && !services.isPend"
      class="col-span-12 content-wrap"
    >
      <CardBase
        class="z-[102] h-fit col-span-12 md:col-span-4 lg:col-span-3 3xl:col-span-2"
        label="info"
      >
        <CardItemList
          :items="[
            {
              label: 'total',
              value: Object.keys(services.setup).length - 1,
            },
            {
              label: 'scheduler',
              value: '',
            },
            {
              label: 'ui',
              value: '',
            },
          ]"
        />
      </CardBase>
      <CardBase
        class="z-[101] h-fit col-span-12 md:col-span-8 lg:col-span-4 3xl:col-span-3"
      >
        <div class="col-span-12 flex">
          <CardLabel label="services" />
          <PluginRefresh @refresh="refresh()" />
        </div>
        <SettingsLayout
          class="flex w-full col-span-12"
          label="Select service"
          name="services-list"
        >
          <SettingsSelect
            @inp="(v) => changeServ(v)"
            v-if="services.activeService"
            :settings="{
              id: 'services-list',
              value:
                services.activeService === 'new' ? '' : services.activeService,
              values: Object.keys(services.setup).filter(
                (item) => item !== 'new'
              ),
              placeholder: 'Services',
            }"
          />
        </SettingsLayout>
        <div class="col-span-12 flex justify-center mt-2">
          <ButtonBase
            @click="services.activeService = 'new'"
            color="valid"
            size="normal"
            class="text-sm"
            >Create new service</ButtonBase
          >
        </div>
        <div class="col-span-12 flex flex-col justify-center items-center mt-2">
          <hr class="line-separator z-10 w-full" />
          <p class="dark:text-gray-500 text-xs text-center mt-1 mb-2">
            <span class="mx-0.5">
              <SettingsUploadSvgWarning class="scale-90" />
            </span>
            Switching services will reset unsaved changes
          </p>
        </div>
      </CardBase>
      <CardBase
        label="plugins"
        class="z-[100] col-span-12 md:col-span-12 lg:col-span-5 3xl:col-span-4 grid grid-cols-12 relative"
      >
        <SettingsLayout
          class="flex w-full col-span-12 2xl:col-span-6"
          label="Select plugin"
          name="plugins"
        >
          <SettingsSelect
            @inp="(v) => (services.activePlugin = v)"
            :settings="{
              id: 'plugins',
              value: services.activePlugin,
              values: services.activePlugins,
              placeholder: 'Search',
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12 2xl:col-span-6"
          label="Setting search"
          name="keyword"
        >
          <SettingsInput
            @inp="(v) => (filters.keyword = v)"
            :settings="{
              id: 'keyword',
              type: 'text',
              value: '',
              placeholder: 'label',
            }"
          />
        </SettingsLayout>
        <SettingsLayout
          class="flex w-full col-span-12 2xl:col-span-6"
          label="Setting method"
          name="keyword"
        >
          <SettingsSelect
            @inp="(v) => (filters.method = v)"
            :settings="{
              id: 'keyword',
              value: 'all',
              values: getMethodList(),
              placeholder: 'Search',
            }"
          />
        </SettingsLayout>
      </CardBase>

      <CardBase
        v-if="services.activeService"
        class="z-10 col-span-12 grid grid-cols-12 relative"
      >
        <CardLabel
          class="text-xl border-b pb-2 mb-4"
          :label="
            services.activeService === 'new'
              ? 'CREATE NEW SERVICE'
              : `SERVICE ${services.activeService}`
          "
        />
        <div class="col-span-12" v-for="(value, key) in services.setup">
          <PluginStructure
            v-if="services.activeService === key"
            :serviceName="key"
            :plugins="value"
            :active="services.activePlugin"
          />
        </div>
        <div class="col-span-12 flex w-full justify-center mt-8 mb-2">
          <ButtonBase @click="sendServConf()" color="valid" size="lg">
            SAVE
          </ButtonBase>
        </div>
      </CardBase>
    </div>
  </Dashboard>
</template>
