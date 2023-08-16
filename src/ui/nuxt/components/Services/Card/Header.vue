<script setup>
const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  method: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <h5
    class="transition duration-300 ease-in-out text-center sm:text-left mb-1 font-bold dark:text-white/90"
  >
    {{ props.name }}
  </h5>
  <h6
    class="text-center sm:text-left mb-2 font-semibold text-gray-600 dark:text-white/80"
  >
    {{ props.method }}
  </h6>
</template>
