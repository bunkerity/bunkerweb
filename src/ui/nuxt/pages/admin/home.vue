<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const { data, pending, error } = await useFetch("/api/instances", {
  method: "GET",
});

const props = defineProps({
  href: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  count: {
    type: String,
    required: true,
  },
  detailArr: {
    type: Array,
    required: true,
  },
  svgCtnrClass: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <NuxtLayout name="dashboard">
    <HomeCardStructure
      :href="'/admin/instances'"
      :name="'instances'"
      :count="'3'"
      :detailArr="[
        {
          text: 'error',
          num: '0',
          textClass: 'text-red-500',
          numClass: 'text-red-500',
        },
        {
          text: 'working',
          num: '3',
          textClass: 'text-green-500',
          numClass: 'text-green-500',
        },
      ]"
    >
      <HomeCardSvgVersion />
    </HomeCardStructure>
  </NuxtLayout>
</template>
