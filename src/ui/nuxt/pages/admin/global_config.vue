<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const { data, pending, error } = await useFetch("/api/plugins", {
  method: "GET",
});
</script>

<template>
  <NuxtLayout name="dashboard">
    <TabStructure :list="data" />
  </NuxtLayout>
</template>
