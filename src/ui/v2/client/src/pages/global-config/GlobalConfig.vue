<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import ButtonBase from "@components/Button/Base.vue";
import CardBase from "@components/Card/Base.vue";
import CardLabel from "@components/Card/Label.vue";
import PluginRefresh from "@components/Plugin/Refresh.vue";
import PluginStructure from "@components/Plugin/Structure.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import { reactive, computed, onMounted, onUpdated, watch } from "vue";
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
const plugins = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
  // Default plugin to display, first of list (before any filter)
  activePlugin: "",
  activePlugins: [],
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    if (
      plugins.isErr ||
      plugins.isPend ||
      !plugins.data ||
      plugins.data.length === 0 ||
      conf.isErr ||
      conf.isPend ||
      !conf.data ||
      conf.data.length === 0
    ) {
      plugins.active = "";
      return [];
    }
    // Duplicate base data
    const cloneGlobalPlugin = getPluginsByContext(
      JSON.parse(JSON.stringify(plugins.data)),
      "global",
    );
    const cloneGlobalConf = JSON.parse(JSON.stringify(conf.data["global"]));
    // Format and keep only global config
    const setPlugins = setPluginsData(cloneGlobalPlugin);
    const mergeConf = addConfToPlugins(setPlugins, cloneGlobalConf);
    // Filter data to display
    const filter = getSettingsByFilter(mergeConf, filters);

    // Get remain plugin after filter
    // Use active service but is impersonal (no specific service logic)
    const remainPlugins = [];
    filter.forEach((item) => {
      item["isMatchFilter"] ? remainPlugins.push(item.name) : false;
    });
    plugins.activePlugins = remainPlugins;

    // Set first plugin as active if none
    if (!plugins.activePlugin)
      plugins.activePlugin =
        plugins.activePlugins.length > 0 ? plugins.activePlugins[0] : "";

    // Case active plugin before update, need some check
    if (plugins.activePlugin) {
      // Case prev active plugin passed filter
      const isPlugin =
        plugins.activePlugins.indexOf(plugins.activePlugin) !== -1
          ? true
          : false;

      // Case not, set first passed one or empty
      if (!isPlugin) {
        plugins.activePlugin =
          plugins.activePlugins.length > 0 ? plugins.activePlugins[0] : "";
      }
    }

    return filter;
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
  plugins.isPend = true;
  await fetchAPI(
    "/api/config?methods=1&new_format=1",
    "GET",
    null,
    conf,
    feedbackStore.addFeedback,
  );
  await fetchAPI(
    "/api/plugins",
    "GET",
    null,
    plugins,
    feedbackStore.addFeedback,
  );
}

onMounted(async () => {
  await getGlobalConf();
});

// Refetch and reset all states
function resetValues() {
  filters.label = "";
  config.$reset();
}

function refresh() {
  getGlobalConf();
  resetValues();
}

async function sendConf() {
  await fetchAPI(
    "/api/config/global?method=ui",
    "PUT",
    config.data["global"],
    null,
    feedbackStore.addFeedback,
  );
}
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="conf.isErr || plugins.isErr"
      :isPend="plugins.isPend"
      :textState="{
        isPend: 'Try retrieve global config',
        isErr: 'Error retrieving global config',
      }"
    />
    <div
      v-if="!plugins.isErr && !plugins.isPend"
      class="col-span-12 content-wrap"
    >
      <CardBase
        class="z-100 h-fit col-span-12 md:col-span-5 lg:col-span-4 3xl:col-span-3 grid grid-cols-12 relative"
      >
        <div class="col-span-12 flex">
          <CardLabel label="global config" />
          <PluginRefresh @refresh="refresh()" />
        </div>
        <SettingsLayout
          class="flex w-full col-span-12"
          label="Select plugin"
          name="plugins"
        >
          <SettingsSelect
            @inp="(v) => (plugins.activePlugin = v)"
            :settings="{
              id: 'plugins',
              value: plugins.activePlugin,
              values: plugins.activePlugins,
              placeholder: 'Search',
            }"
          />
        </SettingsLayout>
      </CardBase>
      <CardBase
        label="filter"
        class="z-10 h-fit col-span-12 md:col-span-7 lg:col-span-5 3xl:col-span-3 grid grid-cols-12 relative"
      >
        <SettingsLayout
          class="flex w-full col-span-12 md:col-span-6"
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
          class="flex w-full col-span-12 md:col-span-6"
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
        <PluginStructure
          :plugins="plugins.setup"
          :active="plugins.activePlugin"
        />
        <div class="col-span-12 flex w-full justify-center mt-8 mb-2">
          <ButtonBase @click="sendConf()" color="valid" size="lg">
            SAVE
          </ButtonBase>
        </div>
      </CardBase>
    </div>
  </Dashboard>
</template>
