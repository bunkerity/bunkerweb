<script setup>
import { useModalStore } from "@store/services.js";

const modalStore = useModalStore();

const props = defineProps({
  hostname: {
    type: String,
    required: false,
    default: "",
  },
});
</script>
<template>
  <button
    v-if="props.hostname"
    :aria-describedby="`clone-${props.hostname}`"
    aria-controls="service-settings-modal"
    :aria-expanded="modalStore.isOpen ? 'true' : 'false'"
    class="dark:brightness-90 z-20 mx-1 bg-emerald-500 hover:bg-emerald-500/80 focus:bg-emerald-500/80 inline-block p-3 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer leading-normal text-xs ease-in tracking-tight-rem shadow-xs bg-150 bg-x-25 active:opacity-85 hover:shadow-md"
  >
    <span :id="`clone-${props.hostname}`" class="sr-only">
      {{ $t("services_clone_desc") }}
    </span>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      class="w-5 h-5 fill-white"
      role="img"
      aria-hidden="true"
    >
      <path
        fill-rule="evenodd"
        d="M17.663 3.118c.225.015.45.032.673.05C19.876 3.298 21 4.604 21 6.109v9.642a3 3 0 0 1-3 3V16.5c0-5.922-4.576-10.775-10.384-11.217.324-1.132 1.3-2.01 2.548-2.114.224-.019.448-.036.673-.051A3 3 0 0 1 13.5 1.5H15a3 3 0 0 1 2.663 1.618ZM12 4.5A1.5 1.5 0 0 1 13.5 3H15a1.5 1.5 0 0 1 1.5 1.5H12Z"
        clip-rule="evenodd"
      />
      <path
        d="M3 8.625c0-1.036.84-1.875 1.875-1.875h.375A3.75 3.75 0 0 1 9 10.5v1.875c0 1.036.84 1.875 1.875 1.875h1.875A3.75 3.75 0 0 1 16.5 18v2.625c0 1.035-.84 1.875-1.875 1.875h-9.75A1.875 1.875 0 0 1 3 20.625v-12Z"
      />
      <path
        d="M10.5 10.5a5.23 5.23 0 0 0-1.279-3.434 9.768 9.768 0 0 1 6.963 6.963 5.23 5.23 0 0 0-3.434-1.279h-1.875a.375.375 0 0 1-.375-.375V10.5Z"
      />
    </svg>
  </button>
</template>
