<script setup>
import { defineProps, computed, onMounted } from "vue";
import { useUUID } from "@utils/global.js";

/**
  @name Icon/Status.vue
  @description This component is a icon used with status.
    @example
  {
    id: "instance-1",
    status: "success",
    statusClass: "col-span-12",
  }
  @param {string} id - The id of the status icon.
  @param {string} [status="info"] - The color of the icon between error, success, warning, info
  @param {string} [statusClass=""] - Additional class, for example to use with grid system.
*/

const props = defineProps({
  id: {
    type: String,
    required: false,
    default: "",
  },
  status: {
    type: String,
    required: true,
    default: "info",
  },
  statusClass: {
    type: String,
    required: false,
    default: "",
  },
});

const status = reactive({
  id: props.id,
});

const statusDesc = computed(() => {
  if (props.status === "success")
    return ["dashboard_status_success", "status active or success."];
  if (props.status === "error")
    return ["dashboard_status_error", "status inactive or error."];
  if (props.status === "warning")
    return ["dashboard_status_warning", "status warning or alert."];
  if (props.status === "info")
    return ["dashboard_status_info", "status loading or waiting or unknown."];
});

onMounted(() => {
  status.id = useUUID(status.id);
});
</script>
<template>
  <div :class="[props.statusClass, 'status-svg-container']">
    <div
      role="img"
      :aria-labelledby="`status-${status.id}`"
      :class="[props.status, 'status-icon']"
    ></div>
    <p :id="`status-${status.id}`" class="sr-only">
      {{ $t(statusDesc[0], statusDesc[1]) }}
    </p>
  </div>
</template>
