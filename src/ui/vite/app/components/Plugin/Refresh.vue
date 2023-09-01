<script setup>
const button = reactive({
  rotate: "",
});

function refresh() {
  button.rotate = "btn-spin";
  setTimeout(() => {
    button.rotate = "";
  }, 2000);
}

const emits = defineEmits(["refresh"]);
</script>

<template>
  <button
    @click="$emit('refresh', refresh())"
    class="mt-2 ml-1 px-1 bg-sky-500 text-white rounded relative -translate-y-2 hover:brightness-95 dark:brightness-95 dark:hover:brightness-90 transition"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke-width="1.5"
      stroke="currentColor"
      :class="[button.rotate]"
      class="pointer-events-none w-5 h-5 mb-0.5"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
      />
    </svg>
  </button>
</template>

<style>
.btn-spin {
  animation: 2s spin linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
