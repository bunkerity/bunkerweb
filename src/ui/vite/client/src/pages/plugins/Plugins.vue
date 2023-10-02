<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import SettingsUploadStructure from "@components/Settings/Upload/Structure.vue";
import PluginList from "@components/Plugin/List.vue";
import { reactive, computed, onMounted } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { getPluginsByFilter } from "@utils/plugins.js";

const feedbackStore = useFeedbackStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  name: "",
  type: "",
});

// Plugins data to render components
const plugins = reactive({
  isPend: false,
  isErr: false,
  // Never modify this unless refetch
  base: [],
  total: computed(() => plugins.base.length),
  internal: computed(
    () => plugins.base.filter((item) => item["external"] === false).length
  ),
  external: computed(
    () => plugins.base.filter((item) => item["external"] === true).length
  ),
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    // Filter data to display
    const cloneBase = JSON.parse(JSON.stringify(plugins.base));
    const filter = getPluginsByFilter(cloneBase, filters);
    return filter;
  }),
});

async function getPlugins() {
  await fetchAPI(
    "/api/global-config",
    "GET",
    null,
    plugins.isPend,
    plugins.isErr,
    feedbackStore.addFeedback
  );
}

onMounted(async () => {
  await getPlugins();
});
</script>

<template>
  <Dashboard>
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
      v-if="!plugins.isPend && !plugins.isErr"
      class="h-fit col-span-12"
      label="plugin list"
    >
      <PluginList :items="plugins.setup" />
    </CardBase>
  </Dashboard>
</template>
