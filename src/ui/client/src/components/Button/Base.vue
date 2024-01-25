<script setup>
import { defineProps, reactive, onUpdated } from "vue";

const props = defineProps({
  // valid || delete || info
  color: {
    type: String,
  },
  // sm || normal || lg || xl
  size: {
    type: String,
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
});

const button = reactive({
  showLoading: false,
});

// Wait few ms before showing loading
onUpdated(() => {
  if (!props.isLoading) return (button.showLoading = false);
  setTimeout(() => {
    button.showLoading = true;
  }, 300);
});
</script>

<template>
  <button :class="[`btn btn-${props.color} btn-${props.size}`]">
    <slot></slot>
    <svg
      v-if="props.isLoading && button.showLoading"
      aria-hidden="true"
      role="img"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke-width="1.5"
      stroke="currentColor"
      class="w-6 h-6 btn-spin ml-2"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
      />
    </svg>
  </button>
</template>

<style scope>
.btn-spin {
  animation: 2s spin linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}
</style>
