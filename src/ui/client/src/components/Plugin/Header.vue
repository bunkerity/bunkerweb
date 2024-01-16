<script setup>
import { defineProps } from "vue";

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  desc: {
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
  <div class="col-span-12" data-setting-header>
    <label
      :for="props.id"
      class="transition duration-300 ease-in-out ml-2 font-bold uppercase dark:text-white/90 mb-0"
    >
      {{ props.name }} <span>{{ props.version }}</span>
    </label>
    <div
      class="transition duration-300 ease-in-out dark:opacity-90 ml-2 text-sm mb-2 dark:text-gray-400"
    >
      {{ props.desc }}
    </div>
  </div>
</template>
