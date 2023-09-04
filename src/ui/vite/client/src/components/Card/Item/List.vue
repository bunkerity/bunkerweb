<script setup>
import { defineProps } from "vue";

const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <div class="col-span-12 flex flex-col items-start justify-start">
    <div
      v-for="item in props.items"
      class="col-span-12 mx-2 flex items-start my-2"
    >
      <h2
        class="transition tracking-normal duration-300 ease-in-out font-bold mb-0 font-sans text-sm leading-normal uppercase text-black dark:text-white dark:opacity-80"
      >
        {{ item.label }}
      </h2>
      <p
        class="transition tracking-normal duration-300 ease-in-out pl-2 col-span-1 mb-0 font-sans text-sm font-semibold leading-normal uppercase text-gray-700 dark:text-gray-300"
      >
        {{ item.value }}
      </p>
    </div>
  </div>
</template>
