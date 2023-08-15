<script setup>
const props = defineProps({
  title: {
    type: String,
    required: false,
  },
});
</script>

<template>
  <div class="card grid grid-cols-12 h-fit">
    <h2
      v-if="props.title"
      class="h-fit col-span-12 uppercase text-xl mb-2 mx-2 font-bold dark:text-white/90"
    >
      {{ props.title }}
    </h2>
    <slot></slot>
  </div>
</template>
