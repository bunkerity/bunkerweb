<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import HomeCardStructure from "@components/Home/Card/Structure.vue";
import HomeCardSvgVersion from "@components/Home/Card/Svg/Version.vue";
import { reactive, computed, onMounted } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";

const feedbackStore = useFeedbackStore();

const instances = reactive({
  isPend: false,
  isErr: false,
  data: [],
  count: computed(() => instances.data.length),
  up: computed(() =>
    instances.data.filter((item) => item.status === "up").length.toString()
  ),
  down: computed(() =>
    instances.data.filter((item) => item.status !== "up").length.toString()
  ),
});

async function getInstances() {
  await fetchAPI(
    "/api/instances",
    "GET",
    null,
    instances,
    feedbackStore.addFeedback
  );
}

onMounted(async () => {
  await getInstances();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-span-6 2xl:col-span-4"
      :isErr="instances.isErr"
      :isPend="instances.isPend"
      :isData="instances.data ? true : false"
    />
    <HomeCardStructure
      v-if="!instances.isPend && !instances.isErr && instances.data"
      :href="'/admin/instances'"
      :name="'instances'"
      :count="instances.count"
      :detailArr="[
        {
          text: 'up',
          num: instances.up,
          textClass: 'text-green-500',
          numClass: 'text-green-500',
        },
        {
          text: 'stop',
          num: instances.down,
          textClass: 'text-red-500',
          numClass: 'text-red-500',
        },
      ]"
    >
      <HomeCardSvgVersion />
    </HomeCardStructure>
  </Dashboard>
</template>
