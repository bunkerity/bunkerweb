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
  defaultDate: {
    type: [String, Number, Date],
    required: false,
    default: null,
  },
  noPickBeforeStamp: {
    type: [String, Number],
    required: false,
    default: "",
  },
  noPickAfterStamp: {
    type: [String, Number],
    required: false,
    default: "",
  },
  inpClass: {
    type: String,
    required: false,
  },
});

const date = reactive({
  isInvalid: false,
  isValid: false,
  format: "m/d/Y H:i:S",
});

let datepicker;
let currStamp;
onMounted(() => {
  datepicker = flatpickr(`#${props.settings.id}`, {
    locale: "en",
    dateFormat: date.format,
    defaultDate: props.defaultDate,
    enableTime: true,
    enableSeconds: true,
    time_24hr: true,
    minuteIncrement: 1,
    onChange(selectedDates, dateStr, instance) {
      console.log(dateStr);
      datepicker.setDate(`${dateStr}h`);
    },
  });
});

function checkToSend(date) {
  currStamp = Date.parse(date);
  // Check pick is in interval
  if (props.noPickBeforeStamp && currStamp < props.noPickBeforeStamp)
    setInvalid(props.noPickBeforeStamp);
  if (props.noPickAfterStamp && currStamp > props.noPickAfterStamp)
    setInvalid(props.noPickAfterStamp);
  // Run whatever, if invalid this will override
  setValid();
  return { timestamp: currStamp, date: new Date(currStamp) };
}

function setInvalid(dateToSet) {
  currStamp = dateToSet;
  datepicker.setDate(currStamp);
  date.isInvalid = true;
  setTimeout(() => {
    date.isInvalid = false;
  }, 1000);
}

function setValid() {
  date.isValid = true;
  setTimeout(() => {
    date.isValid = false;
  }, 1000);
}

const emits = defineEmits(["inp"]);
</script>

<template>
  <div class="relative flex items-center">
    <input
      @change="(v) => $emit('inp', checkToSend(v.target.value))"
      type="text"
      :class="[
        date.isInvalid ? 'invalid' : '',
        !date.isInvalid && date.isValid ? 'valid' : '',
        'input-regular cursor-pointer',
        props.inpClass,
      ]"
      :id="props.settings.id"
      :required="
        props.settings.id === 'SERVER_NAME' || props.settings.required || false
          ? true
          : false
      "
      :disabled="props.settings.disabled || false"
      :name="props.settings.id"
      :placeholder="'mm/dd/yyyy h:m:s'"
      pattern="/^(0[1-9]|1[0-2])\/(0[1-9]|1\d|2\d|3[01])\/\d{4}$/g"
    />
  </div>
</template>
