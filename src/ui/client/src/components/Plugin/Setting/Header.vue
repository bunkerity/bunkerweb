<script setup>
import { defineProps } from "vue";
import PopoverSetting from "@components/Popover/Setting.vue";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  help: {
    type: String,
    required: true,
  },
});
</script>
<template>
  <div role="group" class="flex items-center my-1 relative">
    <h5 class="input-title">
      {{ props.label }}
    </h5>
    <!-- popover -->
    <div class="relative">
      <PopoverSetting tag="div"> {{ props.help }}</PopoverSetting>
    </div>
  </div>
  <!-- end title and info -->
</template>
