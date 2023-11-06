<script setup>
import { defineProps } from "vue";

const props = defineProps({
  id: {
    type: Number,
    required: true,
  },
  type: {
    type: String,
    required: true,
  },
  method: {
    type: [Number, String],
    required: true,
  },
  apiMethod: {
    type: [Number, String],
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
  date: {
    type: [Number, String, Date],
    required: true,
  },
});
</script>

<template>
  <div
    data-flash-message
    :class="[
      props.type === 'error' ? 'bg-red-500' : '',
      props.type === 'success' ? 'bg-green-500' : '',
      props.type !== 'success' && props.type !== 'error' ? 'bg-sky-500' : '',
    ]"
    class="my-1.5 border relative p-4 w-11/12 rounded-lg hover:scale-102 transition shadow-md break-words dark:brightness-90"
  >
    <div class="flex justify-between align-top items-start">
      <h5 class="text-lg mb-0 text-white">
        {{ `${props.title} ${props.type}` }}
      </h5>
    </div>
    <p class="text-white mt-2 mb-0 text-sm">{{ props.message }}</p>
    <p class="text-white mt-2 mb-0 text-xs italic">
      {{ props.method }} | {{ props.apiMethod }}
    </p>
    <p class="text-white mt-2 mb-0 text-xs text-right">{{ props.date }}</p>
  </div>
</template>
