<script setup>
const props = defineProps({
  settings: {
    type: Object,
  },
});

const filterSettings = getSettingsSimple(props.settings);
onMounted(() => {
  console.log(filterSettings);
});
</script>

<template>
  <div
    v-for="setting in filterSettings"
    data-setting-container
    class="ml-2 mr-4 md:ml-3 md:mr-6 xl:ml-4 xl:mr-8 my-2 md:my-3 col-span-12 md:col-span-6 2xl:col-span-4"
  >
    <PluginSettingHeader :label="setting.label" :help="setting.help" />
    <PluginInput v-if="setting.type === 'text'" :setting="setting" />
    <PluginSelect v-if="setting.type === 'select'" :setting="setting" />
    <PluginCheckbox v-if="setting.type === 'check'" :setting="setting" />
  </div>
</template>
