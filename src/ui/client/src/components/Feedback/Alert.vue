<script setup>
import { defineProps, defineEmits } from "vue";

const props = defineProps({
  id: {
    type: [Number, String],
    required: true,
  },
  type: {
    type: String,
    required: true,
  },
  status: {
    type: [Number, String],
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
});

const emits = defineEmits(["close"]);
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
        {{ `${props.status} ${props.type}` }}
      </h5>
      <button
        @click="$emit('close', props.id)"
        data-close-flash-message
        type="button"
        class="absolute right-8 top-2"
      >
        <svg
          class="cursor-pointer fill-white dark:opacity-80 absolute h-5 w-5"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 320 512"
        >
          <path
            d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
          ></path>
        </svg>
      </button>
    </div>
    <p class="text-white mt-2 mb-0 text-sm">{{ props.message }}</p>
  </div>
</template>
