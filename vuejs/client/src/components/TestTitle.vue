<script setup>
const props = defineProps({
    // id && value && method
    title : {
        type: String,
        required: true,
    },
});
</script>

<template>
    <div class="flex flex-col items-center justify-center h-full">
        <h1 class="text-4xl font-bold">{{ title }}</h1>
    </div>
</template>