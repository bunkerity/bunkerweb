<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import { reactive, computed, onMounted } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import FileManagerStructure from "@components/FileManager/Structure.vue";

const feedbackStore = useFeedbackStore();

const customConf = reactive({
  isPend: false,
  isErr: false,
  data: [],
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
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6 2xl:col-span-4 2xl:col-start-5"
      :isErr="customConf.isErr"
      :isPend="customConf.isPend"
      :isData="customConf.data ? true : false"
    />
    <FileManagerStructure class="col-span-12" />
  </Dashboard>
</template>
