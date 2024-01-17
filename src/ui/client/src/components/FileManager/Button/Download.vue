<script setup>
import { useModalStore } from "@store/configs.js";

const modalStore = useModalStore();
</script>

<template>
  <button
    :aria-expanded="modalStore.isOpen ? 'true' : 'false'"
    aria-controls="file-manager-modal"
    class="file-manager-item-btn"
  >
    <span class="flex justify-start items-center">
      <svg
        aria-hidden="true"
        role="img"
        class="h-6 w-6 stroke-sky-500"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.5"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M9 12.75l3 3m0 0l3-3m-3 3v-7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>

      <span class="file-manager-item-btn-text">
        {{ $t("action_download") }}
      </span>
    </span>
  </button>
</template>
