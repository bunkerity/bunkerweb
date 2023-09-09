<script setup>
import { defineProps } from "vue";

const props = defineProps({
  header: {
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
  <div class="w-full col-span-12 grid grid-cols-12 pl-2">
    <label
      v-for="(item, id) in props.header"
      :class="[
        props.positions[id],
        id === props.positions.length - 1 ? 'pl-5' : '',
        id === 0 ? 'pl-3' : '',
      ]"
      class="dark:text-gray-300 pb-1 text-sm font-bold m-0 border-b border-gray-400"
    >
      {{ item }}
    </label>
  </div>
</template>
