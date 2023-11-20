<script setup>
import { defineProps } from "vue";

const props = defineProps({
  details: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <div
    v-for="detail in props.details"
    class="w-full grid grid-cols-12 justify-items-center sm:justify-items-start gap-2 mt-4 mb-6 ml-3 sm:ml-1"
  >
    <div class="flex items-center col-span-12 sm:col-span-6 2xl:col-span-4">
      <p
        class="transition duration-300 ease-in-out dark:opacity-90 font-bold mb-0 font-sans text-sm leading-normal uppercase dark:text-gray-500"
      >
        {{ detail.name }}
      </p>
      <p
        class="transition duration-300 ease-in-out dark:opacity-90 pl-2 mb-0 font-sans text-sm font-semibold leading-normal uppercase dark:text-gray-500"
      >
        <span class="sr-only">{{
          detail.isActive
            ? $t("services.card.detail.state.active")
            : $t("services.card.detail.state.inactive")
        }}</span>
        <svg
          v-if="detail.isActive"
          class="h-4 w-4 fill-green-500"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 512 512"
        >
          <path
            d="M470.6 105.4c12.5 12.5 12.5 32.8 0 45.3l-256 256c-12.5 12.5-32.8 12.5-45.3 0l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0L192 338.7 425.4 105.4c12.5-12.5 32.8-12.5 45.3 0z"
          />
        </svg>
        <svg
          v-if="!detail.isActive"
          class="h-4 w-4 fill-red-500"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 320 512"
        >
          <path
            d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
          />
        </svg>
      </p>
    </div>
  </div>
</template>
