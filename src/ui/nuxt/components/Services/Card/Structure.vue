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
  redirect: {
    type: String,
    required: true,
  },
  details: {
    type: Array,
    required: true,
  },
  settings: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <div
    class="dark:brightness-110 overflow-hidden hover:scale-102 transition col-span-12 lg:col-span-6 3xl:col-span-4 p-4 w-full shadow-md break-words bg-white dark:bg-slate-850 dark:shadow-dark-xl rounded-2xl bg-clip-border"
  >
    <ServicesCardHeader :name="props.name" :method="props.method" />

    <ServicesDetails :details="props.details" />

    <ServicesButtonContainer>
      <ServicesButtonRedirect :redirect="props.redirect" />
      <ServicesButtonEdit />
      <ServicesButtonDelete v-if="props.method === 'ui'" />
    </ServicesButtonContainer>
  </div>
</template>
