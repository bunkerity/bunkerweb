<script setup>
import Dashboard from "../../layouts/Dashboard.vue";
import InstanceCard from "../../components/Instance/Card.vue";
import InstanceModalDelete from "../../components/Instance/Modal/Delete.vue";

const {
  data: instList,
  pending: instPend,
  error: instErr,
} = await useFetch("/api/instances", {
  method: "GET",
});

async function updateInstance(data) {
  const {
    data: instAction,
    pending: instActionPend,
    error: instActionErr,
  } = await useFetch(`/api/instances-action`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

async function deleteInstance(data) {
  const {
    data: instAction,
    pending: instActionPend,
    error: instActionErr,
  } = await useFetch(`/api/instances`, {
    method: "DELETE",
    body: JSON.stringify(data),
  });
}

const modal = reactive({
  isOpen: false,
  hostname: "",
});

function openDelModal(hostname) {
  modal.hostname = hostname;
  modal.isOpen = true;
}
</script>

<template>
  <Dashboard>
    <InstanceCard
      v-for="instance in instList"
      :id="instance.server_name"
      :serverName="instance.server_name"
      :hostname="instance.hostname"
      :port="instance.port"
      :method="instance.method"
      _type="unknown"
      :health="true"
      csrfToken="random"
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
