<script setup>
import CardBase from "@components/Card/Base.vue";
import { defineProps } from "vue";

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
  textState: {
    type: Object,
    required: false,
    default: {
      isPend: "Pending data from API",
      isErr: "Error accessing API",
      isData: "No data to display",
    },
  },
});
</script>

<template>
  <div v-if="isErr || isPend || !isData">
    <CardBase :color="props.isErr ? 'error' : 'default'">
      <div class="col-span-12 flex items-center justify-center">
        <p class="m-0 dark:text-white">
          {{
            isPend
              ? props.textState.isPend
              : isErr
              ? props.textState.isErr
              : isData
              ? ""
              : props.textState.isData
          }}
        </p>
      </div>
    </CardBase>
  </div>
</template>
