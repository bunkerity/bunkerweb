<script setup>
const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  positions: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <ul class="w-full col-span-12 grid grid-cols-12">
    <li
      v-for="(item, id) in props.items"
      :class="[props.positions[id]]"
      class="dark:text-gray-300 h-8 text-sm font-bold m-0 pb-2 border-b border-gray-400"
    >
      {{ item }}
    </li>
  </ul>
</template>
