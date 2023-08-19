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
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      label="info"
    >
      <CardItemList
        :items="[
          { label: 'jobs total', value: '12' },
          { label: 'jobs errors', value: '1' },
        ]"
      />
    </CardBase>
    <CardBase
      class="z-10 h-fit col-span-12 md:col-span-8 xl:col-span-8 2xl:col-span-5 3xl:col-span-4"
      label="filter"
    >
      <SettingsLayout class="sm:col-span-6" label="Search" name="keyword">
        <SettingsInput
          :settings="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: 'keyword',
          }"
        />
      </SettingsLayout>
      <SettingsLayout class="sm:col-span-6" label="Success state" name="state">
        <SettingsSelect
          :settings="{
            id: 'state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </SettingsLayout>
      <SettingsLayout class="sm:col-span-6" label="Success state" name="state">
        <SettingsSelect
          :settings="{
            id: 'state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      class="col-span-12 overflow-x-auto overflow-y-visible"
      label="jobs"
    >
    </CardBase>
  </NuxtLayout>
</template>
