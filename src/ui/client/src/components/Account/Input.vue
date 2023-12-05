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
  placeholder: {
    type: String,
    required: true,
  },
  pattern: {
    type: String,
    required: false,
    default: "(.*?)",
  },
  type: {
    type: String,
    required: true,
    default: "text",
  },
  required: {
    type: Boolean,
    required: false,
    default: false,
  },
  maxlength: {
    type: [Number, Boolean],
    required: false,
    default: false,
  },
  minlength: {
    type: [Number, Boolean],
    required: false,
    default: false,
  },
  value: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <label :for="props.name" class="account-label">
    {{ props.label }}
  </label>
  <input
    :type="props.type"
    :id="props.name"
    :name="props.name"
    class="account-input"
    :placeholder="props.placeholder"
    :pattern="props.pattern"
    :required="props.required"
    :maxlength="props.maxlength"
    :minlength="props.minlength"
    :value="props.value"
  />
</template>
