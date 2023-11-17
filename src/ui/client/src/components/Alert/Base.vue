<script setup>
import { defineProps, defineEmits } from "vue";

const props = defineProps({
  message: {
    type: String,
    required: true,
  },
  // error || valid || warning || info
  type: {
    type: String,
    required: true,
  },
});

const emits = defineEmits(["close"]);
</script>

<template>
  <div
    role="alert"
    :class="[
      props.type === 'error' ? 'bg-red-500' : '',
      props.type === 'success' ? 'bg-green-500' : '',
      props.type === 'info' ? 'bg-sky-500' : '',
      props.type === 'warning' ? 'bg-edit-500' : '',
    ]"
    class="my-2 relative px-4 py-2.5 w-full rounded-lg transition shadow-md break-words dark:brightness-90"
  >
    <div class="flex justify-start align-top items-start">
      <p role="alertdialog" class="text-white mb-0 mr-8 text-sm">
        {{ props.message }}
      </p>
      <button @click="$emit('close')" class="absolute right-8 top-3">
        <span class="sr-only">{{
          $t("A11y.alert.base.close_button.aria_description")
        }}</span>
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
  </div>
</template>
