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
    <CardBase
      class="h-fit col-span-12 md:col-span-4 3xl:col-span-3"
      title="info"
    >
      <CardItemList
        :items="[
          { label: 'plugins total', value: '12' },
          { label: 'plugins errors', value: '1' },
        ]"
      />
    </CardBase>
    <CardBase
      title="upload"
      class="h-fit col-span-12 md:col-span-8 xl:col-span-8 2xl:col-span-4"
    >
      <SettingsUploadStructure />
    </CardBase>
    <CardBase
      class="h-fit col-span-12 md:col-span-8 xl:col-span-8 2xl:col-span-4"
      title="filter"
    >
      <SettingsLayout fullWidth title="Search" name="keyword">
        <SettingsInput
          :setting="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: 'keyword',
          }"
        />
      </SettingsLayout>
      <SettingsLayout fullWidth title="Plugin type" name="state">
        <SettingsSelect
          :setting="{
            id: 'state',
            value: 'all',
            values: ['all', 'internal', 'external'],
          }"
        />
      </SettingsLayout>
    </CardBase>
  </NuxtLayout>
</template>
