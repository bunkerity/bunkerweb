<script setup>
const props = defineProps({
  // Case communication with API failed
  isErr: {
    type: Boolean,
    required: true,
  },
  // Case processing to communication with API
  isPend: {
    type: Boolean,
    required: true,
  },
  // Case communication with API worked but no data to display
  isData: {
    type: Boolean,
    required: true,
  },
});
</script>

<template>
  <div v-if="isErr || isPend || !isData" class="min-h-[70vh]">
    <CardBase :color="props.isErr ? 'error' : 'default'">
      <div class="col-span-12 flex items-center justify-center">
        <p class="m-0 dark:text-white">
          {{
            isPend
              ? "Pending data from API"
              : isErr
              ? "Error accessing API"
              : isData
              ? ""
              : "No data to display"
          }}
        </p>
      </div>
    </CardBase>
  </div>
</template>
