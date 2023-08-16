<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const { data, pending, error } = await useFetch("/api/instances", {
  method: "GET",
});
</script>

<template>
  <NuxtLayout name="dashboard">
    <InstanceCard
      v-for="instance in data"
      :id="instance.server_name"
      :name="instance.server_name"
      :hostname="instance.hostname"
      _type="unknown"
      :health="true"
      csrfToken="random"
    />
  </NuxtLayout>
</template>
