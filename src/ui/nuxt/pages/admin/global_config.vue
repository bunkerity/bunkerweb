<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const {
  data: pluginList,
  pending: pluginPend,
  error: pluginErr,
  refresh: pluginRef,
} = await useFetch("/api/plugins", {
  method: "GET",
});

const {
  data: configList,
  pending: configPend,
  error: configErr,
  refresh: configRef,
} = await useFetch("/api/config", {
  method: "GET",
});

const plugin = reactive({
  active: pluginList.value[0]["name"],
  setup: getPluginsByContext(
    addConfToPlugins(pluginList.value, configList.value),
    "global"
  ),
});

function refreshData() {
  pluginRef();
  configRef();
}
</script>

<template>
  <NuxtLayout name="dashboard">
    <div
      v-if="!pluginPend && !pluginErr && !configPend && !configErr"
      class="col-span-12 content-wrap"
    >
      <CardBase
        class="z-100 col-span-12 2xl:col-span-9 row-start-0 row-end-1 md:row-start-2 md:row-end-2 lg:row-auto grid grid-cols-12 relative"
      >
        <div class="col-span-12 flex">
          <CardLabel label="global config" />
          <PluginRefresh @refresh="refreshData()" />
        </div>
        <TabStructure
          :items="plugin.setup"
          :active="plugin.active"
          @tabName="(v) => (plugin.active = v)"
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
            :settings="{
              id: 'keyword',
              type: 'text',
              value: '',
              placeholder: 'Search',
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
        <PluginStructure :plugins="plugin.setup" :active="plugin.active" />
      </CardBase>
    </div>
  </NuxtLayout>
</template>
