<script setup>
useHead({
  title: "My App",
  meta: [{ name: "description", content: "My amazing site." }],
});

const {
  data: jobsList,
  pending: jobsPen,
  error: jobsErr,
} = await useFetch("/api/jobs", {
  method: "GET",
});

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  name: "",
  reload: "",
  success: "",
  every: "",
});

// Plugins data to render components
const jobs = reactive({
  // Never modify this unless refetch
  base: jobsList.value,
  total: Object.values(jobsList.value).length,
  // This run every time reactive data changed (plugin.base or filters)
  setup: computed(() => {
    // Filter data to display
    const cloneBase = JSON.parse(JSON.stringify(jobs.base));
    const filter = getJobsByFilter(cloneBase, filters);
    return filter;
  }),
});

onMounted(() => {
  console.log(jobs.base);
});
</script>

<template>
  <NuxtLayout name="dashboard">
    <CardBase
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      label="info"
    >
      <CardItemList
        :items="[
          { label: 'jobs total', value: jobs.total },
          { label: 'jobs errors', value: '1' },
        ]"
      />
    </CardBase>
    <CardBase
      class="z-10 h-fit col-span-12 md:col-span-8 xl:col-span-8 2xl:col-span-5 3xl:col-span-4"
      label="filter"
    >
      <SettingsLayout class="sm:col-span-6" label="Search" name="keyword">
        <SettingsInput
          @inp="(v) => (filters.name = v)"
          :settings="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: 'keyword',
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        label="Success state"
        name="success-state"
      >
        <SettingsSelect
          @inp="
            (v) =>
              (filters.success =
                v === 'all' ? 'all' : v === 'true' ? true : false)
          "
          :settings="{
            id: 'success-state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="sm:col-span-6"
        label="Reload state"
        name="reload-state"
      >
        <SettingsSelect
          @inp="
            (v) =>
              (filters.reload =
                v === 'all' ? 'all' : v === 'true' ? true : false)
          "
          :settings="{
            id: 'reload-state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </SettingsLayout>
      <SettingsLayout class="sm:col-span-6" label="Interval" name="every">
        <SettingsSelect
          @inp="(v) => (filters.every = v)"
          :settings="{
            id: 'every',
            value: 'all',
            values: useIntervalList(),
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      class="col-span-12 overflow-x-auto overflow-y-visible"
      label="jobs"
    >
      <JobsStructure />
    </CardBase>
  </NuxtLayout>
</template>
