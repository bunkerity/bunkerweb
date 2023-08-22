<script setup>
const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  positions: {
    type: Array,
    required: true,
  },
});

async function downloadFile(data) {
  const {
    data: file,
    pending: filePend,
    error: fileErr,
    refresh: fileRef,
  } = await useFetch(
    `/api/cache?job-name=${data.jobName}&file-name=${data.fileName}`,
    {
      method: "GET",
    }
  );
}
</script>

<template>
  <ul class="col-span-12 w-full">
    <!-- job item-->
    <li
      v-for="(item, id) in props.items"
      class="items-center grid grid-cols-12 border-b border-gray-300 py-2.5"
    >
      <div
        class="break-words flex items-center col-span-12 grid grid-cols-12 text-sm text-gray-400"
        v-for="(data, key) in item"
      >
        <span :class="[props.positions[0]]">{{ key }}</span>
        <span :class="[props.positions[1]]">{{ data["every"] }}</span>
        <span :class="[props.positions[2]]">{{ "history" }}</span>
        <div class="translate-x-3" :class="[props.positions[3]]">
          <JobsSvgState :success="data['reload']" />
        </div>
        <div class="translate-x-4" :class="[props.positions[4]]">
          <JobsSvgState :success="data['history'][0]['success']" />
        </div>
        <div :class="[props.positions[5]]">
          <span>{{ data["history"][0]["end_date"] }}</span>
        </div>
        <div :class="[props.positions[6]]">
          <SettingsSelect
            v-if="data['cache'].length > 0"
            @inp="(v) => downloadFile({ jobName: key, fileName: v })"
            :settings="{
              id: 'cache-files',
              value: 'select to download',
              values: getJobsCacheNames(data['cache']),
            }"
          />
        </div>
      </div>
    </li>
    <!-- end job item-->
  </ul>
</template>
