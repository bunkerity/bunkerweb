<script setup>
import { computed, onMounted, reactive, watch } from "vue";
import Dashboard from "@layouts/Dashboard.vue";
import CardInfo from "@components/Card/Info.vue";
import CardCount from "@components/Card/Count.vue";
import ApiState from "@components/Api/State.vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";
import { contentIndex } from "@utils/tabindex.js";

const refreshStore = useRefreshStore();

watch(refreshStore, () => {
  getData();
});

const logsStore = useLogsStore();
logsStore.setTags(["plugin", "core", "antibot"]);

const feedbackStore = useFeedbackStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  search: "",
  reason: "all",
});

const plugin = reactive({
  isPend: false,
  isErr: false,
  data: [],
  count: computed(() => {
    return plugin.data.count;
  }),
});

async function getData() {
  plugin.isPend = true;
  plugin.isErr = false;
  return;
  const getData = await fetchAPI(
    "/api/antibot",
    "POST",
    null,
    plugin,
    feedbackStore.addFeedback,
  );
}

onMounted(() => {
  getData();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="plugin.isErr"
      :isPend="plugin.isPend"
      :textState="{
        isPend: $t('api_pending', { name: $t('dashboard_plugins') }),
        isErr: $t('api_error', { name: $t('dashboard_plugins') }),
      }"
    />
    <div class="col-span-12 grid grid-cols-12 gap-4">
      <CardInfo
        class="col-span-12 md:col-span-6 lg:col-span-4 3xl:col-span-3"
        :label="$t('plugin_info')"
        :text="$t('antibot_info')"
      />
      <CardCount
        class="col-span-12 md:col-span-6 lg:col-span-4 3xl:col-span-3"
        :label="$t('antibot_challenge')"
        :counr="plugin.count"
        :detail="$t('antibot_challenge_detail')"
        detailColor="info"
      />
    </div>
  </Dashboard>
</template>
