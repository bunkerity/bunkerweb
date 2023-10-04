<script setup>
const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  version: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <label
    :for="props.name"
    class="my-1 transition duration-300 ease-in-out text-sm sm:text-md font-bold m-0 dark:text-gray-300"
  >
    {{ props.label }} <span v-if="props.version">{{ props.version }}</span>
  </label>
</template>
