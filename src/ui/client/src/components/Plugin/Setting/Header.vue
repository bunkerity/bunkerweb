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
  id: {
    type: String,
    required: true,
  },
});
</script>
<template>
  <div class="flex items-center my-1 relative">
    <label :for="props.id" class="input-title">
      {{ props.label }}
    </label>
    <!-- popover -->
    <div class="relative">
      <PopoverSetting :label="props.label" tag="div">
        {{ props.help }}
      </PopoverSetting>
    </div>
  </div>
  <!-- end title and info -->
</template>
