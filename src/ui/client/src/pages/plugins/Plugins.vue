<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import SettingsUploadStructure from "@components/Settings/Upload/Structure.vue";
import PluginList from "@components/Plugin/List.vue";
import PluginModalDelete from "@components/Plugin/Modal/Delete.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { getPluginsByFilter, pluginI18n } from "@utils/plugins.js";
import ApiState from "@components/Api/State.vue";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";
import { useI18n } from "vue-i18n";
const { locale, fallbackLocale } = useI18n();
// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  getPlugins();
});

const logsStore = useLogsStore();
logsStore.setTags(["plugin"]);

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
  data: [],
  total: computed(() => plugins.data.length),
  internal: computed(
    () => plugins.data.filter((item) => item["external"] === false).length
  ),
  external: computed(
    () => plugins.data.filter((item) => item["external"] === true).length
  ),
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    if (plugins.isPend || plugins.isErr || plugins.data.length === 0) return [];

    // Filter data to display
    const cloneBase = JSON.parse(JSON.stringify(plugins.data));
    // translate
    pluginI18n(cloneBase, locale.value, fallbackLocale.value);

    const filter = getPluginsByFilter(cloneBase, filters);
    return filter;
  }),
});

async function getPlugins() {
  await fetchAPI(
    "/api/plugins",
    "GET",
    null,
    plugins,
    feedbackStore.addFeedback
  );
}

const modalDel = reactive({
  isOpen: false,
  pluginId: "",
  pluginName: "",
  pluginDesc: "",
});

function openDelModal(v) {
  modalDel.pluginId = v.id;
  modalDel.pluginName = v.name;
  modalDel.pluginDesc = v.description;
  modalDel.isOpen = true;
}

onMounted(() => {
  getPlugins();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="plugins.isErr"
      :isPend="plugins.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_plugins') }),
        isErr: $t('api_error', { name: $t('dashboard_plugins') }),
      }"
    />
    <CardBase
      v-if="!plugins.isErr && !plugins.isPend && plugins.setup.length > 0"
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      :label="$t('dashboard_plugins')"
    >
      <CardItemList
        :items="[
          {
            label: $t('plugins_total'),
            value: plugins.total,
          },
          {
            label: $t('plugins_internal'),
            value: plugins.internal,
          },
          {
            label: $t('plugins_external'),
            value: plugins.external,
          },
        ]"
      />
    </CardBase>
    <CardBase
      v-if="!plugins.isErr && !plugins.isPend"
      :label="$t('action_upload')"
      class="h-fit col-span-12 md:col-span-8 2xl:col-span-4 3xl:col-span-3"
    >
      <SettingsUploadStructure />
    </CardBase>
    <CardBase
      v-if="!plugins.isErr && !plugins.isPend"
      class="z-10 h-fit col-start-1 col-end-13 md:col-start-5 md:col-end-13 2xl:col-span-5 3xl:col-span-4"
      :label="$t('dashboard_filter')"
    >
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('plugins_filter_search')"
        name="keyword"
      >
        <SettingsInput
          @inp="(v) => (filters.name = v)"
          :settings="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: $t('plugins_filter_search_placeholder'),
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        :label="$t('plugins_filter_type')"
        name="state"
      >
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
      :label="$t('dashboard_plugins')"
    >
      <PluginList @delete="(v) => openDelModal(v)" :items="plugins.setup" />
    </CardBase>
    <PluginModalDelete
      @close="modalDel.isOpen = false"
      @pluginDelete="useRefreshStore.refresh()"
      :isOpen="modalDel.isOpen"
      :pluginId="modalDel.pluginId"
      :pluginName="modalDel.pluginName"
      :pluginDesc="modalDel.pluginDesc"
    />
  </Dashboard>
</template>
