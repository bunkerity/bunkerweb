<script setup>
import SettingsLabel from "@components/Settings/Label.vue";
import { defineProps } from "vue";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  version: {
    type: String,
    required: false,
    default: "",
  },
  showLabel: {
    type: Boolean,
    required: false,
    default: true,
  },
});
</script>

<template>
  <div class="col-span-12 flex flex-col px-2 py-1">
    <SettingsLabel
      :show="props.showLabel"
      :label="props.label"
      :name="props.name"
      :version="props.version"
    />
    <slot></slot>
  </div>
</template>
