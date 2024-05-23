<script setup>
/** 
  @name Title/CardContent.vue
  @description This component is similar to TitleCard but with a lower size.
  This can be used outside of the card container.
    @example
  {
    title: "Total Users",
    titleClass: "text-lg"
  }
  @param {string} title -  Can be a translation key or by default raw text.
  @param {string} [titleClass=""] - Additional class, useful when component is used directly on a grid system
*/

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
  <h2 v-if="props.title" :class="[props.titleClass, 'card-content-title']">
    {{ $t(props.title, props.title) }}
  </h2>
</template>
