<script setup>
import { reactive, defineEmits, defineProps } from "vue";

const props = defineProps({
  // id && type && disabled && required && value
  settings: {
    type: Object,
    required: true,
  },
  inpClass: {
    type: String,
    required: false
  }
});

const inp = reactive({
  value : props.settings.value,
})

const emits = defineEmits(["inp"]);
</script>

<template>
  <div class="relative flex items-center">
    <input
      v-model="inp.value"
      @input="$emit('inp', inp.value)"
      :type="props.settings.type"
      :id="props.settings.id"
      :class="['input-regular', props.inpClass]"
      :required="props.settings.id === 'SERVER_NAME' || props.settings.required || false ? true : false"
      :disabled="props.settings.disabled || false"
      :placeholder="props.settings.placeholder || ''"
      :pattern="props.settings.pattern || '(?s).*'"
      :name="props.settings.id"
      :value="inp.value"
    />
  </div>
</template>
