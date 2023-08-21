<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

// Base data to work with
const {
  data: globalConfList,
  pending: globalConfPend,
  error: globalConfErr,
  refresh: globalConfRef,
} = await useFetch("/api/global_config", {
  method: "GET",
});

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  label: "",
});

// Plugins data to render components
const plugins = reactive({
  // Never modify this unless refetch
  base: globalConfList.value,
  // Default plugin to display, first of list (before any filter)
  active: globalConfList.value[0]["name"],
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    // Filter data to display
    const cloneBase = JSON.parse(JSON.stringify(plugins.base));
    const filter = getPluginsByFilter(cloneBase, filters);
    // Check if prev plugin or no plugin match filter
    plugins.active =
      filter.length !== 0 ? filter[0]["name"] : globalConfList.value[0]["name"];
    return filter;
  }),
});

// Refetch and reset all states
function reset() {
  globalConfRef();
  filters.label = "";
  plugins.active = globalConfList.value[0]["name"];
}
</script>

<template>
  <NuxtLayout name="dashboard">
    <div
      v-if="!globalConfPend && !globalConfErr"
      class="col-span-12 content-wrap"
    >
      <CardBase
        class="z-100 col-span-12 2xl:col-span-9 row-start-0 row-end-1 md:row-start-2 md:row-end-2 lg:row-auto grid grid-cols-12 relative"
      >
        <div class="col-span-12 flex">
          <CardLabel label="global config" />
          <PluginRefresh @refresh="reset()" />
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
            @input="(v) => (filters.label = v.target.value)"
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
          <ButtonBase @click="updateConf()" valid>SAVE</ButtonBase>
        </div>
      </CardBase>
    </div>
  </NuxtLayout>
</template>
