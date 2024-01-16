<script setup>
import ServicesCardHeader from "@components/Services/Card/Header.vue";
import ServicesDetails from "@components/Services/Details.vue";
import ServicesButtonContainer from "@components/Services/Button/Container.vue";
import ServicesButtonRedirect from "@components/Services/Button/Redirect.vue";
import ServicesButtonEdit from "@components/Services/Button/Edit.vue";
import ServicesButtonDelete from "@components/Services/Button/Delete.vue";
import { defineProps } from "vue";

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

    <ServicesDetails :name="props.name" :details="props.details" />

    <ServicesButtonContainer>
      <ServicesButtonRedirect :name="props.name" :redirect="props.redirect" />
      <ServicesButtonEdit :name="props.name" />
      <ServicesButtonDelete :name="props.name" v-if="props.method === 'ui'" />
    </ServicesButtonContainer>
  </div>
</template>
