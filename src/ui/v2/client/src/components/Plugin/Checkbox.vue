<script setup>
import { useConfigStore } from "@store/settings.js";
import { getModes, getDefaultMethod } from "@utils/settings.js";
import { reactive, defineProps } from "vue";

const props = defineProps({
  setting: {
    type: Object,
    required: true,
  },
  serviceName: {
    type: String,
    required: false,
    default: "",
  },
});

const checkbox = reactive({
  id: props.setting.id,
  context: props.setting.context,
  value: props.setting.value || props.setting.default,
  defaultValue: props.setting.default,
  method: props.setting.method || getDefaultMethod(),
  defaultMethod: getDefaultMethod(),
});

// Modes with special method and logic
const modes = getModes();

const config = useConfigStore();

function updateCheckbox() {
  checkbox.value = checkbox.value === "yes" ? "no" : "yes";
}
</script>

<template>
  <div class="relative mb-7 md:mb-0 z-10">
    <input
      @click="
        () => {
          updateCheckbox();
          config.updateConf(
            props.serviceName || checkbox.context,
            checkbox.id,
            checkbox.value,
          );
        }
      "
      :id="checkbox.id"
      :name="checkbox.id"
      :data-default-method="
        modes.indexOf(checkbox.method) !== -1 ? 'mode' : checkbox.method
      "
      :data-default-value="checkbox.defaultValue"
      :disabled="
        modes.indexOf(checkbox.method) !== -1 ||
        (checkbox.method !== 'ui' && checkbox.method !== 'default')
          ? true
          : false
      "
      :aria-checked="checkbox.value === 'yes' ? 'true' : 'false'"
      checked
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
