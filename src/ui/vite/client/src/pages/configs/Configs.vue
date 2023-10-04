<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import { reactive, computed, onMounted } from "vue";
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

async function getCustomConf() {
  await fetchAPI(
    "/api/custom_configs",
    "GET",
    null,
    customConf,
    feedbackStore.addFeedback,
  );
}

async function getConfig() {
  await fetchAPI(
    "/api/config?methods=1&new_format=1",
    "GET",
    null,
    conf,
    feedbackStore.addFeedback,
  );
}

onMounted(async () => {
  await getConfig();
  await getCustomConf();
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
          { label: 'configs total', value: customConf.total },
          { label: 'configs global', value: customConf.global },
          { label: 'configs services', value: customConf.service },
        ]"
      />
    </CardBase>
    <CardBase
      label="configs"
      class="z-[100] col-span-12 md:col-span-8 lg:col-span-6 2xl:col-span-5 3xl:col-span-4 grid grid-cols-12 relative"
    >
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6"
        label="Search path"
        name="pathKeyword"
      >
        <SettingsInput
          @inp="(v) => (filters.pathKeyword = v)"
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
        label="Search name"
        name="nameKeyword"
      >
        <SettingsInput
          @inp="(v) => (filters.nameKeyword = v)"
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
        label="Show services folders"
        name="show-service"
      >
        <SettingsCheckbox
          @inp="(v) => (filters.showServices = v)"
          :settings="{
            id: 'show-service',
            value: 'yes',
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6"
        label="Only path with .conf"
        name="show-only-conf"
      >
        <SettingsCheckbox
          @inp="(v) => (filters.showOnlyCaseConf = v)"
          :settings="{
            id: 'show-only-conf',
            value: 'no',
          }"
        />
      </SettingsLayout>
    </CardBase>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6 2xl:col-span-4 2xl:col-start-5"
      :isErr="customConf.isErr"
      :isPend="customConf.isPend"
      :isData="customConf.data ? true : false"
    />
    <FileManagerStructure
      v-if="customConf.setup.length > 0"
      :config="customConf.setup"
      class="col-span-12"
    />
  </Dashboard>
</template>
