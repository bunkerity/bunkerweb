<script setup>
import { useDelModalStore } from "@store/services.js";

const delModalStore = useDelModalStore();

const props = defineProps({
  hostname: {
    type: String,
    required: false,
    default: "",
  },
  method: {
    type: String,
    required: true,
    default: "",
  },
});
</script>
<template>
  <button
    v-if="props.method === 'ui' || props.method === 'default'"
    :aria-describedby="`delete-${props.hostname}`"
    aria-controls="service-delete-modal"
    :aria-expanded="delModalStore.isOpen ? 'true' : 'false'"
    class="dark:brightness-90 z-20 mx-1 bg-red-500 hover:bg-red-500/80 focus:bg-red-500/80 inline-block p-3 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer leading-normal text-xs ease-in tracking-tight-rem shadow-xs bg-150 bg-x-25 active:opacity-85 hover:shadow-md"
  >
    <span :id="`delete-${props.hostname}`" class="sr-only">
      {{ $t("services_delete_desc") }}
    </span>
    <svg
      role="img"
      aria-hidden="true"
      class="w-5 h-5 fill-white"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 448 512"
    >
      <path
        d="M135.2 17.7L128 32H32C14.3 32 0 46.3 0 64S14.3 96 32 96H416c17.7 0 32-14.3 32-32s-14.3-32-32-32H320l-7.2-14.3C307.4 6.8 296.3 0 284.2 0H163.8c-12.1 0-23.2 6.8-28.6 17.7zM416 128H32L53.2 467c1.6 25.3 22.6 45 47.9 45H346.9c25.3 0 46.3-19.7 47.9-45L416 128z"
      />
    </svg>
  </button>
</template>
