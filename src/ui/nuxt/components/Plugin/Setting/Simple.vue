<script setup>
const props = defineProps({
  settings: {
    type: Array,
  },
});
</script>

<template>
  <div
    v-for="setting in filterSettings"
    data-setting-container
    class="mx-0 sm:mx-4 my-2 col-span-12 md:mx-6 md:my-3 md:col-span-6 2xl:mx-6 2xl:my-3 2xl:col-span-4"
  >
    <SettingInput v-if="setting.type === 'input'" :setting="setting" />
    <SettingSelect v-if="setting.type === 'select'" :setting="setting" />
    <SettingCheckbox v-if="setting.type === 'checkbox'" :setting="setting" />
  </div>
</template>
