<script setup>
import { reactive, defineProps } from "vue";

const props = defineProps({
  // id && value && method
  settings: {
    type: Object,
    required: true,
  },
});

const checkbox = reactive({
  value: props.settings.value,
});

const emits = defineEmits(["inp"]);

function updateValue() {
  checkbox.value = checkbox.value === "yes" ? "no" : "yes";
  return checkbox.value;
}
</script>

<template>
  <div class="relative z-10">
    <input
      @click="$emit('inp', updateValue())"
      :id="props.settings.id"
      :name="props.settings.id"
      :aria-checked="checkbox.value === 'yes' ? 'true' : 'false'"
      :checked="checkbox.value === 'yes' ? true : false"
      :class="[checkbox.value === 'yes' ? 'check' : '', 'checkbox']"
      type="checkbox"
      :value="checkbox.value"
    />

    <svg
      v-show="checkbox.value === 'yes'"
      class="checkbox-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
    >
      <path
        class="pointer-events-none"
        d="M470.6 105.4c12.5 12.5 12.5 32.8 0 45.3l-256 256c-12.5 12.5-32.8 12.5-45.3 0l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0L192 338.7 425.4 105.4c12.5-12.5 32.8-12.5 45.3 0z"
      ></path>
    </svg>
  </div>
</template>
