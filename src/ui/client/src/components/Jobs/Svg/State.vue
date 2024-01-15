<script setup>
import { defineProps } from "vue";

const props = defineProps({
  success: {
    type: Boolean,
    required: false,
  },
});
</script>

<template>
  <div
    class="bg-white w-3 h-3 rounded -z-10 translate-x-1 translate-y-1.5 absolute"
  ></div>
  <svg
    role="img"
    aria-hidden="true"
    v-if="props.success"
    class="fill-green-500 h-5 w-5 z-10"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 512 512"
  >
    <path
      d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM369 209L241 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L335 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"
    />
  </svg>
  <svg
    role="img"
    aria-hidden="true"
    v-if="!props.success"
    class="fill-red-500 h-5 w-5 z-10"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 512 512"
  >
    <path
      d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM175 175c9.4-9.4 24.6-9.4 33.9 0l47 47 47-47c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9l-47 47 47 47c9.4 9.4 9.4 24.6 0 33.9s-24.6 9.4-33.9 0l-47-47-47 47c-9.4 9.4-24.6 9.4-33.9 0s-9.4-24.6 0-33.9l47-47-47-47c-9.4-9.4-9.4-24.6 0-33.9z"
    />
  </svg>
</template>
