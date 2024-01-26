<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import {
  generateConfTree,
  getCustomConfByFilter,
} from "@utils/custom_configs.js";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsCheckbox from "@components/Settings/Checkbox.vue";
import { useFeedbackStore } from "@store/global.js";
import FileManagerStructure from "@components/FileManager/Structure.vue";
import FileManagerModal from "@components/FileManager/Modal.vue";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";
import { useModalStore } from "@store/configs.js";
import { contentIndex } from "@utils/tabindex.js";

// Refresh when related btn is clicked
const modalStore = useModalStore();
const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  getData();
});

const logsStore = useLogsStore();
logsStore.setTags(["custom_config"]);

const feedbackStore = useFeedbackStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  pathKeyword: "",
  nameKeyword: "",
  showServices: "yes",
  showOnlyCaseConf: "no",
});

const conf = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
});

const customConf = reactive({
  isPend: false,
  isErr: false,
  data: [],
  total: computed(() => customConf.data.length || 0),
  global: computed(
    () => customConf.data.filter((item) => !item["service_id"]).length || 0,
  ),
  service: computed(
    () => customConf.data.filter((item) => item["service_id"]).length || 0,
  ),
  setup: computed(() => {
    if (
      conf.isPend ||
      conf.isErr ||
      conf.data.length === 0 ||
      customConf.isPend ||
      customConf.isErr
    ) {
      return [];
    }
    const config = JSON.parse(JSON.stringify(conf.data));
    const services = Object.keys(config["services"]);
    const confTree = generateConfTree(customConf.data, services);
    const filterManager = getCustomConfByFilter(confTree, filters);
    return filterManager;
  }),
});

async function getCustomConf(isFeedback = true) {
  await fetchAPI(
    "/api/custom_configs",
    "GET",
    null,
    customConf,
    isFeedback ? feedbackStore.addFeedback : null,
  );
}

async function getConfig(isFeedback = true) {
  await fetchAPI(
    "/api/config?methods=1&new_format=1",
    "GET",
    null,
    conf,
    isFeedback ? feedbackStore.addFeedback : null,
  );
}

async function getData() {
  await getConfig();
  await getCustomConf();
}

onMounted(() => {
  getData();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="customConf.isErr"
      :isPend="conf.isPend || customConf.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_configs') }),
        isErr: $t('api_error', { name: $t('dashboard_configs') }),
      }"
    />
    <CardBase
      v-if="
        !customConf.isPend && !customConf.isErr && !conf.isPend && !conf.isErr
      "
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      :label="$t('dashboard_info')"
    >
      <CardItemList
        :items="[
          {
            label: $t('custom_conf_total'),
            value: customConf.total,
          },
          {
            label: $t('custom_conf_global'),
            value: customConf.global,
          },
          {
            label: $t('custom_conf_services'),
            value: customConf.service,
          },
        ]"
      />
    </CardBase>
    <CardBase
      v-if="
        !customConf.isPend && !customConf.isErr && !conf.isPend && !conf.isErr
      "
      :label="$t('dashboard_filter')"
      class="z-[100] col-span-12 md:col-span-8 2xl:col-span-6 3xl:col-span-5 grid grid-cols-12 relative"
    >
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6"
        :label="$t('custom_conf_filter_search_path')"
        name="pathKeyword"
      >
        <SettingsInput
          @inp="(v) => (filters.pathKeyword = v)"
          :tabId="modalStore.isOpen ? '-1' : contentIndex"
          :settings="{
            id: 'pathKeyword',
            type: 'text',
            value: '',
            placeholder: 'base/service/conf',
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6"
        :label="$t('custom_conf_filter_search_name')"
        name="nameKeyword"
      >
        <SettingsInput
          @inp="(v) => (filters.nameKeyword = v)"
          :tabId="modalStore.isOpen ? '-1' : contentIndex"
          :settings="{
            id: 'nameKeyword',
            type: 'text',
            value: '',
            placeholder: 'label',
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6"
        :label="$t('custom_conf_filter_show_services_folders')"
        name="show-service"
      >
        <SettingsCheckbox
          @inp="(v) => (filters.showServices = v)"
          :tabId="modalStore.isOpen ? '-1' : contentIndex"
          :settings="{
            id: 'show-service',
            value: 'yes',
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6 capitalize-first"
        :label="$t('custom_conf_filter_show_path_with_conf')"
        name="show-only-conf"
      >
        <SettingsCheckbox
          @inp="(v) => (filters.showOnlyCaseConf = v)"
          :tabId="modalStore.isOpen ? '-1' : contentIndex"
          :settings="{
            id: 'show-only-conf',
            value: 'no',
          }"
        />
      </SettingsLayout>
    </CardBase>
    <FileManagerModal :aria-hidden="modalStore.isOpen ? 'false' : 'true'" />

    <FileManagerStructure
      v-if="
        !customConf.isPend &&
        !customConf.isErr &&
        !conf.isPend &&
        !conf.isErr &&
        customConf.setup.length > 0
      "
      :config="customConf.setup"
      class="col-span-12"
    />
  </Dashboard>
</template>
