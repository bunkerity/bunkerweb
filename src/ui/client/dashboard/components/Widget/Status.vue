<script setup>
import { defineProps, computed, onBeforeMount, reactive } from "vue";
import { useUUID } from "@utils/global.js";

/**
 *  @name Icon/Status.vue
 *  @description This component is a icon used with status.
 *  @example
 *  {
 *    id: "instance-1",
 *    status: "success",
 *    statusClass: "col-span-12",
 *  }
 *  @param {String} id - The id of the status icon.
 *  @param {String} [status="info"] - The color of the icon between error, success, warning, info
 *  @param {String} [statusClass=""] - Additional class, for example to use with grid system.
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
  id: "",
});

const statusDesc = computed(() => {
  if (props.status === "success") return "dashboard_status_success";
  if (props.status === "error") return "dashboard_status_error";
  if (props.status === "warning") return "dashboard_status_warning";
  if (props.status === "info") return "dashboard_status_info";
});

onBeforeMount(() => {
  status.id = useUUID(props.id);
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
      {{ $t(statusDesc) }}
    </p>
  </div>
</template>
