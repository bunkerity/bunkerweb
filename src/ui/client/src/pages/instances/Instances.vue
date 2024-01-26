<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import InstanceCard from "@components/Instance/Card.vue";
import InstanceModalEdit from "@components/Instance/Modal/Edit.vue";
import InstanceModalAdd from "@components/Instance/Modal/Add.vue";
import InstanceButtonAdd from "@components/Instance/Button/Add.vue";
import { reactive, computed, onMounted, watch } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import ApiState from "@components/Api/State.vue";
import { useLogsStore } from "@store/logs.js";
import { useRefreshStore } from "@store/global.js";
import {
  useAddModalStore,
  useDelModalStore,
  useEditModalStore,
} from "@store/instances.js";
import { contentIndex } from "@utils/tabindex.js";

const addModalStore = useAddModalStore();
const delModalStore = useDelModalStore();
const editModalStore = useEditModalStore();
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
        isPend: $t('api_pending', { name: $t('dashboard_instances') }),
        isErr: $t('api_error', { name: $t('dashboard_instances') }),
      }"
    />
    <InstanceModalAdd />
    <InstanceModalEdit />
    <div
      class="col-span-12 relative flex justify-center min-w-0 break-words rounded-2xl bg-clip-border"
    >
      <InstanceButtonAdd
        :tabindex="
          addModalStore.isOpen || delModalStore.isOpen || editModalStore.isOpen
            ? -1
            : contentIndex
        "
        v-if="!instances.isErr && !instances.isPend"
      />
    </div>
    <div
      class="col-span-12 grid grid-cols-12 gap-y-4 gap-x-0 md:gap-x-4"
      v-if="!instances.isErr && !instances.isPend"
    >
      <InstanceCard
        v-for="instance in instances.data"
        :id="instance.server_name"
        :serverName="instance.server_name"
        :hostname="instance.hostname"
        :port="instance.port"
        :method="instance.method"
        :status="instance.status"
      />
    </div>
  </Dashboard>
</template>
