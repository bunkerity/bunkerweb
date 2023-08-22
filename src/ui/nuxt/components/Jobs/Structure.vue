<script setup>
const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  header: {
    type: Array,
    required: false,
  },
  positions: {
    type: Array,
    required: true,
    // Give col-span for each col
  },
});
</script>

<template>
  <div
    class="min-w-[1100px] w-full grid grid-cols-12 rounded p-2 col-span-12 overflow-x-hidden overflow-y-visible"
  >
    <JobsHeader :items="props.header" :positions="props.positions" />
    <JobsContent :items="props.items" :positions="props.positions" />
  </div>
</template>
