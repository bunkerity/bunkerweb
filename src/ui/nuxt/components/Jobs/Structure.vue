<script setup>
const props = defineProps({
  content: {
    type: Array,
    required: true,
  },
  header: {
    type: Array,
    required: false,
  },
  positions: {
    type: Array,
    required: false,
    // Give col-span for each col
    default: [
      "col-span-3",
      "col-span-2",
      "col-span-1",
      "col-span-1",
      "col-span-1",
      "col-span-3",
      "col-span-1",
    ],
  },
});
</script>

<template>
  <div
    class="min-w-[1000px] w-full grid grid-cols-12 rounded p-2 col-span-12 overflow-x-hidden overflow-y-visible"
  >
    <JobsHeader :items="props.header" :positions="props.positions" />
    <JobsContent :items="props.content" :positions="props.positions" />
  </div>
</template>
