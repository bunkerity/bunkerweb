<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
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
          { label: 'plugins total', value: '12' },
          { label: 'plugins errors', value: '1' },
        ]"
      />
    </CardBase>
    <CardBase
      label="upload"
      class="h-fit col-span-12 md:col-span-8 2xl:col-span-4 3xl:col-span-3"
    >
      <SettingsUploadStructure />
    </CardBase>
    <CardBase
      class="z-10 h-fit col-start-1 col-end-13 md:col-start-5 md:col-end-13 2xl:col-span-5 3xl:col-span-4"
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
      <SettingsLayout class="sm:col-span-6" label="Plugin type" name="state">
        <SettingsSelect
          :settings="{
            id: 'state',
            value: 'all',
            values: ['all', 'internal', 'external'],
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase class="h-fit col-span-12" label="plugin list">
      <PluginList />
    </CardBase>
  </NuxtLayout>
</template>
