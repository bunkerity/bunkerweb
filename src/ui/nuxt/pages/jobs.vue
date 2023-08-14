<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const { data, pending, error } = await useFetch("/api/jobs", {
  method: "GET",
});
</script>

<template>
  <NuxtLayout name="dashboard">
    <div class="card grid grid-cols-12 col-span-6">
      <SettingsLayout class="col-span-6" title="Search" name="keyword">
        <SettingsInput
          :setting="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: 'keyword',
          }"
        />
      </SettingsLayout>
      <SettingsLayout class="col-span-6" title="Type" name="keyword">
        <SettingsSelect
          :setting="{
            id: 'keyword',
            type: 'text',
            value: 'all',
            values: ['all', 'day', 'month'],
            placeholder: 'keyword',
          }"
        />
      </SettingsLayout>
    </div>
  </NuxtLayout>
</template>
