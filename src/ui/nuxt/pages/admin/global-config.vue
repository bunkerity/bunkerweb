<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

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
  <NuxtLayout name="dashboard">
    <CardBase
      class="col-span-4 col-start-5"
      :class="[
        plugins.isErr && !globalConfPend ? '!bg-red-500' : '',
        !plugins.isErr && !globalConfPend && plugins.setup.length === 0
          ? '!bg-sky-500'
          : '',
        !plugins.isErr && globalConfPend === 0 ? '!bg-yellow-500' : '',
      ]"
      v-if="plugins.isErr || globalConfPend"
    >
      <div class="col-span-12 flex items-center justify-center">
        <p class="m-0 dark:text-white">
          {{
            plugins.isErr && !globalConfPend
              ? "Error accessing api"
              : !plugins.isErr && !globalConfPend && plugins.setup.length === 0
              ? "No data to display"
              : !plugins.isErr && globalConfPend
              ? "Fetching data"
              : ""
          }}
        </p>
      </div>
    </CardBase>
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
  </NuxtLayout>
</template>
