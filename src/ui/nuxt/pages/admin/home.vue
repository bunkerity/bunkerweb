<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const feedbackStore = useFeedbackStore();

const {
  data: instancesList,
  pending: instancesPend,
  refresh: instancesRef,
} = await useFetch("/api/instances", {
  method: "GET",
  onResponse({ request, response, options }) {
    // Process the response data
    feedbackStore.addFeedback(
      response._data.type,
      response._data.status,
      response._data.message,
    );
  },
});

const instances = reactive({
  isErr: instancesList.value.type === "error" ? true : false,
  data: instancesList.value.type === "error" ? {} : instancesList.value.data,
  count: computed(() => instances.data.length),
});
</script>

<template>
  <NuxtLayout name="dashboard">
    <ApiState
      class="col-span-12 md:col-span-6 2xl:col-span-4"
      :isErr="instances.isErr"
      :isPend="instancesPend"
      :isData="instances.data ? true : false"
    />
    <HomeCardStructure
      v-if="!instancesPend && !instances.isErr && instances.data"
      :href="'/admin/instances'"
      :name="'instances'"
      :count="instances.count"
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
