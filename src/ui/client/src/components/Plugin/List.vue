<script setup>
import { defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";

const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  isModalOpen: {
    type: Boolean,
    required: true,
  },
});

const emits = defineEmits(["delete"]);
</script>

<template>
  <ul class="col-span-12 grid grid-cols-12 gap-3 mt-3">
    <li
      v-for="(plugin, id) in props.items"
      class="py-3 min-h-12 relative col-span-12 sm:col-span-6 2xl:col-span-3 p-1 flex justify-between items-center transition rounded bg-gray-100 hover:bg-gray-300 dark:bg-slate-700 dark:hover:bg-slate-800"
    >
      <p
        :class="[
          plugin.external ? 'mr-2' : '',
          'ml-3 mb-0 transition duration-300 ease-in-out dark:opacity-90 text-left text-sm md:text-base text-slate-700 dark:text-gray-200',
        ]"
      >
        {{ plugin.name }}
      </p>
      <div v-if="plugin.external" class="flex items-center">
        <a
          :tabindex="contentIndex"
          v-if="plugin.page"
          class="hover:-translate-y-px"
          :href="plugin.page"
          :aria-describedby="`${plugin.name}-${id}-text`"
        >
          <span :id="`${plugin.name}-${id}-text`" class="sr-only">
            {{ $t("plugins_page_label") }}
          </span>
          <svg
            role="img"
            aria-hidden="true"
            class="h-6 w-6 fill-sky-500 dark dark:brightness-90"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 448 512"
          >
            <path
              d="M288 32c-17.7 0-32 14.3-32 32s14.3 32 32 32h50.7L169.4 265.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L384 141.3V192c0 17.7 14.3 32 32 32s32-14.3 32-32V64c0-17.7-14.3-32-32-32H288zM80 64C35.8 64 0 99.8 0 144V400c0 44.2 35.8 80 80 80H336c44.2 0 80-35.8 80-80V320c0-17.7-14.3-32-32-32s-32 14.3-32 32v80c0 8.8-7.2 16-16 16H80c-8.8 0-16-7.2-16-16V144c0-8.8 7.2-16 16-16h80c17.7 0 32-14.3 32-32s-14.3-32-32-32H80z"
            ></path>
          </svg>
        </a>
        <button
          :tabindex="contentIndex"
          v-if="plugin.method.toLowerCase() !== 'static'"
          @click="
            $emit('delete', {
              id: plugin.id,
              name: plugin.name,
              description: plugin.description,
            })
          "
          type="button"
          aria-controls="plugin-delete-modal"
          :aria-expanded="props.isModalOpen ? 'true' : 'false'"
          :aria-describedby="`${plugin.name}-${id}-delete-text`"
          class="z-20 mx-2 inline-block font-bold text-left text-white uppercase align-middle transition-all cursor-pointer text-xs ease-in tracking-tight-rem hover:-translate-y-px"
        >
          <span :id="`${plugin.name}-${id}-delete-text`" class="sr-only">
            {{ $t("action_delete") }}
          </span>
          <svg
            role="img"
            aria-hidden="true"
            class="h-5 w-5 fill-red-500 dark:brightness-90"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 448 512"
          >
            <path
              d="M135.2 17.7L128 32H32C14.3 32 0 46.3 0 64S14.3 96 32 96H416c17.7 0 32-14.3 32-32s-14.3-32-32-32H320l-7.2-14.3C307.4 6.8 296.3 0 284.2 0H163.8c-12.1 0-23.2 6.8-28.6 17.7zM416 128H32L53.2 467c1.6 25.3 22.6 45 47.9 45H346.9c25.3 0 46.3-19.7 47.9-45L416 128z"
            />
          </svg>
        </button>
      </div>
    </li>
  </ul>
</template>
