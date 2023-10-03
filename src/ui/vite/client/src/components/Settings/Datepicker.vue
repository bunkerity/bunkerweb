<script setup>
import { ref, reactive, defineEmits, defineProps, onMounted } from "vue";
import flatpickr from "flatpickr";
import "@assets/css/datepicker-foundation.css";
import "@assets/css/flatpickr.css";
import "@assets/css/flatpickr.dark.css";

const props = defineProps({
  // id && type && disabled && required && value
  settings: {
    type: Object,
    required: true,
  },
});


onMounted(() => {
  const el = flatpickr(`#${props.settings.id}`, {locale: "en",   dateFormat: "m/d/Y",});
})

const emits = defineEmits(["inp"]);
</script>

<template>
  <div class="relative flex items-center">
    <input
      @change="(v) => $emit('inp', {timestamp : Date.parse(v.target.value), date : new Date(Date.parse(v.target.value))})"
      type="text"
      class="input-regular cursor-pointer"
      :id="props.settings.id"
      :required="props.settings.id === 'SERVER_NAME' || props.settings.required || false ? true : false"
      :disabled="props.settings.disabled || false"
      :name="props.settings.id"
    />
  </div>
</template>
