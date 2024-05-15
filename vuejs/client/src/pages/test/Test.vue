<script setup>
import { reactive, onBeforeMount } from "vue";
import  TestTile from "@components/TestTitle.vue";

// Define reactive properties
const data = reactive({
    // Define properties here
    title : 'No title'
})

// Retrieve default or flask data if available
onBeforeMount(() => {
  const dataEl = document.querySelector('[data-flask]');
  data.title = dataEl.getAttribute('data-flask') && dataEl.getAttribute('data-flask') !== "{{ flask_data }}" ? dataEl.getAttribute('data-flask') : dataEl.getAttribute('data-default-value');
})

</script>

<template>
    <div class="bg-secondary flex flex-col items-center justify-center h-full">
      <TestTile :title="data.title" />
    </div>
</template>
