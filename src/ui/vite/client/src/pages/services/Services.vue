<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import ButtonBase from "@components/Button/Base.vue";
import CardBase from "@components/Card/Base.vue";
import CardLabel from "@components/Card/Label.vue";
import PluginRefresh from "@components/Plugin/Refresh.vue";
import PluginStructure from "@components/Plugin/Structure.vue";
import TabStructure from "@components/Tab/Structure.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { reactive, computed, onMounted, KeepAlive, watch } from "vue";
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

watch(config, () => {
  console.log(config.data);
});

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
  list: [],
  activeTab: "",
  activeService: "",
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
      services.activeTab = "";
      services.list = [];
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
    // And add to list of services
    services.list = [];

    for (const [key, value] of Object.entries(cloneServConf)) {
      const currServPlugin = JSON.parse(JSON.stringify(cloneMultisitePlugin));
      const currServConf = JSON.parse(JSON.stringify(cloneServConf[key]));
      cloneServConf[key] = addConfToPlugins(currServPlugin, currServConf);
      services.list.push(key);
    }

    // Filter data to display for each service
    for (const [key, value] of Object.entries(cloneServConf)) {
      cloneServConf[key] = getSettingsByFilter(cloneServConf[key], filters);
    }
    // Check if prev plugin or no plugin match filter for current display service
    services.activeTab =
      services.activeService &&
      cloneServConf[services.activeService].length !== 0
        ? cloneServConf[services.activeService][0]["name"]
        : "";

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

// Show service data logic
onMounted(async () => {
  await getGlobalConf();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-4 col-start-5"
      :isErr="services.isErr"
      :isPend="services.isPend"
      :isData="true"
    />
    <div
      v-if="!services.isErr && !services.isPend"
      class="col-span-12 content-wrap"
    >
      <CardBase
        class="z-100 col-span-12 2xl:col-span-9 row-start-0 row-end-1 md:row-start-2 md:row-end-2 lg:row-auto grid grid-cols-12 relative"
      >
        <div class="col-span-12 flex">
          <CardLabel label="global config" />
          <PluginRefresh @refresh="refresh()" />
        </div>
        <div class="flex">
          <ButtonBase
            v-for="service in services.list"
            color="primary"
            size="lg"
            class="mx-2"
            @click="
              services.activeService =
                services.activeService === service ? '' : service
            "
            >{{ service }}</ButtonBase
          >
        </div>
      </CardBase>
      <CardBase
        label="filter"
        class="z-10 col-span-12 2xl:col-span-3 row-start-1 row-end-2 md:row-start-0 2xl:row-auto grid grid-cols-12 relative"
      >
        <SettingsLayout
          class="flex w-full col-span-12 md:col-span-6 2xl:col-span-12"
          label="Search"
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
          class="flex w-full col-span-12 md:col-span-6 2xl:col-span-12"
          label="Method"
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
      <CardBase class="col-span-12 grid grid-cols-12 relative">
        <div class="col-span-12" v-for="(value, key) in services.setup">
          <TabStructure
            v-if="services.activeService === key"
            :items="value"
            :active="services.activeTab"
            @tabName="(v) => (services.activeTab = v)"
          />
          <PluginStructure
            v-if="services.activeService === key"
            :serviceName="key"
            :plugins="value"
            :active="services.activeTab"
          />
        </div>
        <div class="col-span-12 flex w-full justify-center mt-8 mb-2">
          <ButtonBase @click="sendConf()" color="valid" size="lg">
            SAVE
          </ButtonBase>
        </div>
      </CardBase>
    </div>
  </Dashboard>
</template>
