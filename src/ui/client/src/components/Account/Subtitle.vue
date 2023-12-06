<script setup>
const props = defineProps({
  title: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <h2 class="col-span-12 block text-left font-bold my-4 text-2xl">
    {{ props.title }}
  </h2>
</template>
