<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const {
  data: pluginList,
  pending: pluginPend,
  error: pluginErr,
} = await useFetch("/api/global-config", {
  method: "GET",
});

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  name: "",
  type: "",
});

// Plugins data to render components
const plugins = reactive({
  // Never modify this unless refetch
  base: pluginList.value,
  total: pluginList.value.length,
  internal: pluginList.value.filter((item) => item["external"] === false)
    .length,
  external: pluginList.value.filter((item) => item["external"] === true).length,
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    // Filter data to display
    const cloneBase = JSON.parse(JSON.stringify(plugins.base));
    const filter = getPluginsByFilter(cloneBase, filters);
    return filter;
  }),
});
</script>

<template>
  <NuxtLayout name="dashboard">
    <CardBase
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      label="info"
    >
      <CardItemList
        :items="[
          { label: 'plugins total', value: plugins.total },
          { label: 'plugins internal', value: plugins.internal },
          { label: 'plugins external', value: plugins.external },
        ]"
      />
    </CardBase>
    <CardBase
      label="upload"
      class="h-fit col-span-12 md:col-span-8 2xl:col-span-4 3xl:col-span-3"
    >
      <SettingsUploadStructure />
    </CardBase>
    <CardBase
      class="z-10 h-fit col-start-1 col-end-13 md:col-start-5 md:col-end-13 2xl:col-span-5 3xl:col-span-4"
      label="filter"
    >
      <SettingsLayout class="sm:col-span-6" label="Search" name="keyword">
        <SettingsInput
          @inp="(v) => (filters.name = v)"
          :settings="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: 'keyword',
          }"
        />
      </SettingsLayout>
      <SettingsLayout class="sm:col-span-6" label="Plugin type" name="state">
        <SettingsSelect
          @inp="
            (v) =>
              (filters.external =
                v === 'all' ? 'all' : v === 'external' ? true : false)
          "
          :settings="{
            id: 'state',
            value: 'all',
            values: ['all', 'internal', 'external'],
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      v-if="!pluginPend && !pluginErr"
      class="h-fit col-span-12"
      label="plugin list"
    >
      <PluginList :items="plugins.setup" />
    </CardBase>
  </NuxtLayout>
</template>
