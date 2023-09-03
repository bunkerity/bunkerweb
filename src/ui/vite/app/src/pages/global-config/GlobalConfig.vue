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

import { useFeedbackStore } from "@store/global.js";
import { useConfigStore } from "@store/settings.js";

const feedbackStore = useFeedbackStore();
const config = useConfigStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  keyword: "",
  method: "",
});

const {
  data: globalConfList,
  pending: globalConfPend,
  refresh: globalConfRef,
} = await useFetch("/api/global-config", {
  method: "GET",
  onResponse({ request, response, options }) {
    // Process the response data
    feedbackStore.addFeedback(
      response._data.type,
      response._data.status,
      response._data.message
    );
  },
});

// Plugins data to render components
const plugins = reactive({
  isErr: globalConfList.value.type === "error" ? true : false,
  // Never modify this unless refetch
  base: globalConfList.value.type === "error" ? [] : globalConfList.value.data,
  // Default plugin to display, first of list (before any filter)
  active:
    globalConfList.value.type === "error"
      ? ""
      : globalConfList.value.data[0]["name"],
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    if (globalConfList.value.type === "error") return [];
    // Filter data to display
    const cloneBase = JSON.parse(JSON.stringify(plugins.base));
    const filter = getSettingsByFilter(cloneBase, filters);
    // Check if prev plugin or no plugin match filter
    plugins.active =
      filter.length !== 0
        ? filter[0]["name"]
        : globalConfList.value.data[0]["name"];
    return filter;
  }),
});

// Refetch and reset all states
function resetValues() {
  filters.label = "";
  plugins.active = globalConfList.value.data[0]["name"];
}

function refresh() {
  globalConfRef();
  resetValues();
}

async function sendConf() {
  const data = JSON.stringify(config.data["global"]);
  await useFetch("/api/global-config", {
    method: "PUT",
    body: data,
    onResponse({ request, response, options }) {
      // Process the response data
      feedbackStore.addFeedback(
        response._data.type,
        response._data.status,
        response._data.message
      );
    },
  });
}
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-4 col-start-5"
      :isErr="plugins.isErr"
      :isPend="globalConfPend"
      :isData="plugins.setup.length > 0 ? true : false"
    />
    <div
      v-if="!plugins.isErr && !globalConfPend"
      class="col-span-12 content-wrap"
    >
      <CardBase
        class="z-100 col-span-12 2xl:col-span-9 row-start-0 row-end-1 md:row-start-2 md:row-end-2 lg:row-auto grid grid-cols-12 relative"
      >
        <div class="col-span-12 flex">
          <CardLabel label="global config" />
          <PluginRefresh @refresh="refresh()" />
        </div>
        <TabStructure
          :items="plugins.setup"
          :active="plugins.active"
          @tabName="(v) => (plugins.active = v)"
        />
      </CardBase>
      <CardBase
        label="filter"
        class="z-10 col-span-12 2xl:col-span-3 row-start-1 row-end-2 md:row-start-0 2xl:row-auto row-end-1 grid grid-cols-12 relative"
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
              values: useMethodList(),
              placeholder: 'Search',
            }"
          />
        </SettingsLayout>
      </CardBase>

      <CardBase class="col-span-12 grid grid-cols-12 relative">
        <PluginStructure :plugins="plugins.setup" :active="plugins.active" />
        <div class="col-span-12 flex w-full justify-center mt-8 mb-2">
          <ButtonBase @click="sendConf()" color="valid" size="lg">
            SAVE
          </ButtonBase>
        </div>
      </CardBase>
    </div>
  </Dashboard>
</template>
