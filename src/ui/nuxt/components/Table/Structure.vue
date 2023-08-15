<script setup>
const props = defineProps({
  content: {
    type: Array,
    required: true,
    default: [
      {
        // To render text
        name: "whitelist",
        last_run: "2023",
        every: "hour",
        // To render svg check / error
        reload: true,
        success: true,
        // To render select
        files: [{ name: "file-1" }],
        // To render button
        run: { name: "test", value: "test" },
      },
    ],
  },
  header: {
    type: Array,
    required: true,
    default: [
      "Name",
      "Last run",
      "Every",
      "Reload",
      "Success",
      "Files",
      "action",
    ],
  },
  positions: {
    type: Array,
    required: true,
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
  <div class="min-w-[1000px] w-full grid grid-cols-12 rounded p-2 col-span-12">
    <TableHeader :items="props.header" :positions="props.positions" />
    <TableContent :items="props.content" :positions="props.positions" />
  </div>
</template>
