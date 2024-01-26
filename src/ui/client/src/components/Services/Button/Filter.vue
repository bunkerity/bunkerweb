<script setup>
import { useFilterStore } from "@store/services.js";

const filterStore = useFilterStore();
</script>
<template>
  <button
    @click="filterStore.isOpen = !filterStore.isOpen"
    aria-controls="service-card-filter-more"
    :aria-expanded="filterStore.isOpen ? 'true' : 'false'"
    class="p-1 dark:bg-sky-500/90 duration-300 dark:opacity-90 flex justify-center items-center font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer bg-sky-500 hover:bg-sky-500/80 focus:bg-sky-500/80 leading-normal text-base ease-in tracking-tight-rem shadow-xs bg-150 bg-x-25 hover:-translate-y-px active:opacity-85 hover:shadow-md"
  >
    <span class="sr-only">{{ $t("services_filter_more_toggle") }}</span>
    <svg
      v-if="!filterStore.isOpen"
      role="img"
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke-width="1.5"
      stroke="currentColor"
      class="pointer-events-none w-6 h-6"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607ZM10.5 7.5v6m3-3h-6"
      />
    </svg>
    <svg
      v-if="filterStore.isOpen"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke-width="1.5"
      stroke="currentColor"
      class="pointer-events-none w-6 h-6"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607ZM13.5 10.5h-6"
      />
    </svg>
  </button>
</template>
