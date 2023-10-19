<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import InstanceCard from "@components/Instance/Card.vue";
import InstanceModalDelete from "@components/Instance/Modal/Delete.vue";
import { reactive, computed, onMounted } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import ApiState from "@components/Api/State.vue";

const feedbackStore = useFeedbackStore();

const modal = reactive({
  delIsOpen: false,
  pingIsOpen: false,
  hostname: "",
});

function openDelModal(hostname) {
  modal.hostname = hostname;
  modal.delIsOpen = true;
}

const instances = reactive({
  isPend: false,
  isErr: false,
  data: [],
  count: computed(() => instances.data.length),
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

async function actionInstance(data) {
  await fetchAPI(
    `/api/instances/${data.hostname}/${data.operation}`,
    "POST",
    null,
    instances,
    feedbackStore.addFeedback
  );
  await getInstances();
}

const ping = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function deleteInstance(data) {
  await fetchAPI(
    `/api/instances/${data.hostname}`,
    "DELETE",
    null,
    instances,
    feedbackStore.addFeedback
  );
  await getInstances();
}

onMounted(async () => {
  await getInstances();
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
      @action="(v) => actionInstance(v)"
      @delete="(hostname) => openDelModal(hostname)"
    />
    <InstanceModalDelete
      @delete="(v) => deleteInstance(v)"
      @close="modal.delIsOpen = false"
      :isOpen="modal.delIsOpen"
      :hostname="modal.hostname"
    />
  </Dashboard>
</template>
