<script setup>
const props = defineProps({
  label: {
    type: String,
    required: false,
  },
});
</script>

<template>
  <h2
    v-if="props.label"
    class="col-span-12 uppercase text-xl mb-2 mx-2 font-bold dark:text-white/90"
  >
    {{ props.label }}
  </h2>
</template>
