<script setup>
const props = defineProps({
  title: {
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
  fullWidth: {
    type: Boolean,
    required: false,
  },
});
</script>

<template>
  <div
    :class="[props.fullWidth ? '' : 'sm:col-span-6 ']"
    class="col-span-12 flex flex-col px-2 py-1"
  >
    <SettingsLabel
      :title="props.title"
      :name="props.name"
      :version="props.version"
    />
    <slot></slot>
  </div>
</template>
