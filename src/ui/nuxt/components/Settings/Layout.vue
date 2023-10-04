<script setup>
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
  noLabel: {
    type: Boolean,
    required: false,
    default: false,
  },
});
</script>

<template>
  <div class="col-span-12 flex flex-col px-2 py-1">
    <SettingsLabel
      v-show="!props.noLabel"
      :label="props.label"
      :name="props.name"
      :version="props.version"
    />
    <slot></slot>
  </div>
</template>
