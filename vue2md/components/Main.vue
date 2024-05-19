<script setup>
/** 
  @name Main.vue
  @description This component is my main layout for my app.
  @example
  {
    title : "My app",
    subtitle : "my subtitle"
  }
  @param {string} title
  @param {string} [subtitle=""] - More information if needed
*/

const props = defineProps({
  // id && value && method
  title: {
    type: String,
    required: true,
  },
  subtitle: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <div>
    <h1>{{ props.title }}</h1>
    <p v-if="props.subtitle">{{ props.subtitle }}</p>
  </div>
</template>
