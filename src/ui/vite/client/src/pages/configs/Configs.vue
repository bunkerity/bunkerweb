<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import CardBase from "@components/Card/Base.vue";
import CardItemList from "@components/Card/Item/List.vue";
import { reactive, computed, onMounted } from "vue";
import { fetchAPI } from "@utils/api.js";
import { generateConfTree } from "@utils/custom_configs.js";
import { useFeedbackStore } from "@store/global.js";
import FileManagerStructure from "@components/FileManager/Structure.vue";

const feedbackStore = useFeedbackStore();

const customConf = reactive({
  isPend: false,
  isErr: false,
  data: [],
  total: computed(() => customConf.data.length),
  global: computed(
    () => customConf.data.filter((item) => !item["service_id"]).length
  ),
  service: computed(
    () => customConf.data.filter((item) => item["service_id"]).length
  ),
  setup: computed(() => {
    const conf = generateConfTree(customConf.data);
    return conf;
  }),
});

async function getConfigs() {
  await fetchAPI(
    "/api/custom_configs",
    "GET",
    null,
    customConf,
    feedbackStore.addFeedback
  );
}

onMounted(async () => {
  await getConfigs();
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
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6 2xl:col-span-4 2xl:col-start-5"
      :isErr="customConf.isErr"
      :isPend="customConf.isPend"
      :isData="customConf.data ? true : false"
    />
    <FileManagerStructure :config="customConf.setup" class="col-span-12" />
  </Dashboard>
</template>
