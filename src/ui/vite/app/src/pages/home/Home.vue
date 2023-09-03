<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import ApiState from "@components/Api/State.vue";
import HomeCardStructure from "@components/Home/Card/Structure.vue";
import HomeCardSvgVersion from "@components/Home/Card/Svg/Version.vue";
import { useFeedbackStore } from "@store/global.js";
import { reactive, computed } from "vue";
import { fetchAPI } from "@utils/api.js";

const feedbackStore = useFeedbackStore();

const instances = reactive({
  isFetch: false,
  isPend: false,
  isErr: false,
  data: {},
  count: computed(() => 1),
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
          text: 'error',
          num: '0',
          textClass: 'text-red-500',
          numClass: 'text-red-500',
        },
        {
          text: 'working',
          num: '3',
          textClass: 'text-green-500',
          numClass: 'text-green-500',
        },
      ]"
    >
      <HomeCardSvgVersion />
    </HomeCardStructure>
  </Dashboard>
</template>
