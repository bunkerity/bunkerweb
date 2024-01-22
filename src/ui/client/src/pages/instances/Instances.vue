<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import InstanceCard from "@components/Instance/Card.vue";
import InstanceModalDelete from "@components/Instance/Modal/Delete.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import ApiState from "@components/Api/State.vue";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();
const feedbackStore = useFeedbackStore();

watch(refreshStore, () => {
  getInstances();
});

const logsStore = useLogsStore();
logsStore.setTags(["instance"]);

const instances = reactive({
  isPend: false,
  isErr: false,
  data: [],
  count: computed(() => instances.data.length),
});

async function getInstances(isFeedback = true) {
  await fetchAPI(
    "/api/instances",
    "GET",
    null,
    instances,
    isFeedback ? feedbackStore.addFeedback : null,
  );
}

onMounted(() => {
  getInstances();
});
</script>

<template>
  <Dashboard>
    <ApiState
      class="col-span-12 md:col-start-4 md:col-span-6"
      :isErr="instances.isErr"
      :isPend="instances.isPend"
      :textState="{
        isPend: 'Try retrieve instances',
        isErr: 'Error retrieving instances',
      }"
    />
    <InstanceCard
      v-for="instance in instances.data"
      :id="instance.server_name"
      :serverName="instance.server_name"
      :hostname="instance.hostname"
      :port="instance.port"
      :method="instance.method"
      :status="instance.status"
    />
    <InstanceModalDelete />
  </Dashboard>
</template>
