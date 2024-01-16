<script setup>
import { defineEmits, defineProps } from "vue";

const props = defineProps({
  redirect: {
    type: String,
    required: true,
  },
});

const emits = defineEmits(["redirect"]);
</script>

<template>
  <a
    @click="$emit('redirect')"
    :href="props.redirect"
    :aria-label="$t('services_redirect_link_label')"
    target="_blank"
    class="dark:brightness-90 z-20 mx-1 bg-sky-500 hover:bg-sky-500/80 focus:bg-sky-500/80 inline-block p-3 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer leading-normal text-xs ease-in tracking-tight-rem shadow-xs bg-150 bg-x-25 active:opacity-85 hover:shadow-md"
  >
    <svg
      role="img"
      aria-hidden="true"
      class="h-6 w-6 fill-white"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 448 512"
    >
      <path
        d="M288 32c-17.7 0-32 14.3-32 32s14.3 32 32 32h50.7L169.4 265.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L384 141.3V192c0 17.7 14.3 32 32 32s32-14.3 32-32V64c0-17.7-14.3-32-32-32H288zM80 64C35.8 64 0 99.8 0 144V400c0 44.2 35.8 80 80 80H336c44.2 0 80-35.8 80-80V320c0-17.7-14.3-32-32-32s-32 14.3-32 32v80c0 8.8-7.2 16-16 16H80c-8.8 0-16-7.2-16-16V144c0-8.8 7.2-16 16-16h80c17.7 0 32-14.3 32-32s-14.3-32-32-32H80z"
      />
    </svg>
  </a>
</template>
