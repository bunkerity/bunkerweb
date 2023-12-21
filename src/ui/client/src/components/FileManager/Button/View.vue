<script setup>
const props = defineProps({
  isModalOpen: {
    type: Boolean,
    required: true,
  },
});
</script>

<template>
  <button
    :aria-expanded="props.isModalOpen ? 'true' : 'false'"
    aria-controls="file-manager-modal"
    class="file-manager-item-btn"
  >
    <span class="flex justify-start items-center">
      <svg
        class="h-5.5 w-5.5 stroke-green-700 dark:brightness-125"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.5"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
        />
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
        />
      </svg>
      <span class="file-manager-item-btn-text">
        {{ $t("action_view") }}
      </span>
    </span>
  </button>
</template>
