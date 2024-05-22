<script setup>
const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  titleClass: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <h1 v-if="props.title" :class="[props.titleClass, 'content-title']">
    {{ $t(props.title, props.title) }}
  </h1>
</template>
