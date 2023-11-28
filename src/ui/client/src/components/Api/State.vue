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
  textState: {
    type: Object,
    required: false,
    default: {
      isPend: "Pending data from API",
      isErr: "Error accessing API",
    },
  },
});
</script>

<template>
  <div
    role="alert"
    :aria-description="$t('dashboard_api_state_desc')"
    v-if="isErr || isPend"
  >
    <CardBase :color="props.isErr ? 'error' : 'pending'">
      <div class="col-span-12 flex items-center justify-center">
        <p role="alertdialog" class="m-0 dark:text-white">
          {{ isErr ? props.textState.isErr : props.textState.isPend }}
        </p>
      </div>
    </CardBase>
  </div>
</template>
