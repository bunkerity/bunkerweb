<script setup>
/** 
  @name Form/Input.vue
  @description This component is custom input to be used with forms.
  @example
  {
    name : "my subtitle"
    value : "P@ssw0rd"
    type : "password"
  }
  @param {string} name
  @param {string} [value=""]
  @param {string} [type="text"]
*/

const props = defineProps({
  // id && value && method
  name: {
    type: String,
    required: true,
  },
  value: {
    type: String,
    required: false,
    default: "",
  },
  type: {
    type: String,
    required: false,
    default: "type",
  },
});
</script>

<template>
  <input :type="props.type" :name="props.name" :value="props.value" />
</template>
