<script setup>
import Dashboard from "@layouts/Dashboard.vue";
import InstanceCard from "@components/Instance/Card.vue";
import InstanceModalDelete from "@components/Instance/Modal/Delete.vue";
import { reactive, computed, onMounted } from "vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";

const feedbackStore = useFeedbackStore();

const modal = reactive({
  isOpen: false,
  hostname: "",
});

function openDelModal(hostname) {
  modal.hostname = hostname;
  modal.isOpen = true;
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

async function updateInstance(data) {
  await fetchAPI(
    `/api/${data.hostname}/${data.operation}`,
    "POST",
    null,
    instances,
    feedbackStore.addFeedback
  );
  await getInstances();
}

async function deleteInstance(data) {
  await fetchAPI(
    "api/instances",
    "DELETE",
    JSON.stringify(data),
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
    <InstanceCard
      v-for="instance in instances.data"
      :id="instance.server_name"
      :serverName="instance.server_name"
      :hostname="instance.hostname"
      :port="instance.port"
      :method="instance.method"
      :status="instance.status"
      @action="(v) => updateInstance(v)"
      @delete="(hostname) => openDelModal(hostname)"
    />
    <InstanceModalDelete
      @delete="(v) => deleteInstance(v)"
      @close="modal.isOpen = false"
      :isOpen="modal.isOpen"
      :hostname="modal.hostname"
    />
  </Dashboard>
</template>
