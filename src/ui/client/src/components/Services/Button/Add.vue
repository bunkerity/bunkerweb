<script setup>
import { useModalStore } from "@store/services.js";

const modalStore = useModalStore();
</script>
<template>
  <div
    class="col-span-12 relative flex justify-center min-w-0 break-words rounded-2xl bg-clip-border"
  >
    <button
      aria-controls="service-settings-modal"
      :aria-expanded="modalStore.isOpen ? 'true' : 'false'"
      class="dark:bg-green-500/90 duration-300 dark:opacity-90 w-80 flex justify-center items-center px-6 py-3 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer bg-green-500 hover:bg-green-500/80 focus:bg-green-500/80 leading-normal text-base ease-in tracking-tight-rem shadow-xs bg-150 bg-x-25 hover:-translate-y-px active:opacity-85 hover:shadow-md"
    >
      <span class="mr-2">{{ $t("services_actions_new") }}</span>
      <svg
        role="img"
        aria-hidden="true"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.5"
        stroke="currentColor"
        class="pointer-events-none w-7 h-7"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
        />
      </svg>
    </button>
  </div>
</template>
