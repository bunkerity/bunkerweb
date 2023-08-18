<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const { data, pending, error } = await useFetch("/api/plugins", {
  method: "GET",
});

const plugin = reactive({
  active: data[0]["name"] || "",
});
</script>

<template>
  <NuxtLayout name="dashboard">
    <TabStructure
      :items="data"
      :active="plugin.active"
      @tabName="(v) => (plugin.active = v)"
    />
    <PluginStructure :active="plugin.active" />
  </NuxtLayout>
</template>
