<script setup>
import { useConfigStore } from "@store/settings.js";
import { getDefaultMethod } from "@utils/settings.js";
import {
  ref,
  reactive,
  watch,
  onMounted,
  onBeforeUpdate,
  defineProps,
} from "vue";

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

const select = reactive({
  id: props.setting.id,
  context: props.setting.context,
  values: props.setting.select,
  value: props.setting.value || props.setting.default, // Value onMount that can ben changed
  valueStatic: props.setting.value || props.setting.default, // Value onMount to compare to add config (don't touch)
  defaultValue: props.setting.default,
  method: props.setting.method.toLowerCase() || getDefaultMethod(),
  defaultMethod: getDefaultMethod(),
  isOpen: false,
});

const selectBtn = ref();
const selectWidth = ref("");
const selectTop = ref("");
const config = useConfigStore();

// EVENTS
function toggleSelect() {
  select.isOpen = select.isOpen ? false : true;
}

function closeSelect() {
  select.isOpen = false;
}

function changeValue(newValue) {
  select.value = newValue;
  closeSelect();
}

// Close select dropdown when clicked outside element
watch(select, () => {
  if (select.isOpen) {
    document.querySelector("body").addEventListener("click", closeOutside);
    window.addEventListener("scroll", updateTop);
  } else {
    document.querySelector("body").removeEventListener("click", closeOutside);
    window.removeEventListener("scroll", updateTop);
  }
});

function updateTop() {
  selectTop.value = `${
    Math.abs(
      selectBtn.value.closest(".plugin-structure").scrollTop -
        selectBtn.value.offsetTop,
    ) + selectBtn.value.clientHeight
  }px`;
}

// Close select when clicked outside logic
function closeOutside(e) {
  try {
    if (e.target !== selectBtn.value) {
      select.isOpen = false;
    }
  } catch (err) {
    select.isOpen = false;
  }
}

onBeforeUpdate(() => {
  selectWidth.value = `${selectBtn.value.clientWidth}px`;
});

onMounted(() => {
  window.addEventListener("resize", () => {
    try {
      selectWidth.value = `${selectBtn.value.clientWidth}px`;
    } catch (err) {}
  });
});
</script>

<template>
  <label class="sr-only" :for="select.id">{{ select.id }}</label>
  <!-- default hidden-->
  <select
    :data-default-method="select.defaultMethod"
    :data-default-value="select.defaultValue"
    :id="select.id"
    :name="select.id"
    :aria-description="$t('inp_select_default_desc')"
    class="hidden"
  >
    <option
      v-for="(value, id) in select.values"
      :value="value"
      :label="value ? value : $t('inp_select_label_empty')"
      :selected="value === select.value ? true : false"
      :id="`${select.id}-option-${id}`"
    >
      {{ value }}
    </option>
  </select>
  <!-- end default hidden-->

  <button
    :aria-controls="`${select.id}-dropdown`"
    :aria-expanded="select.isOpen ? 'true' : 'false'"
    ref="selectBtn"
    :aria-description="$t('inp_select_dropdown_button_desc')"
    :data-select-dropdown="props.setting.id"
    :disabled="
      select.method !== 'ui' && select.method !== 'default' ? true : false
    "
    @click="toggleSelect()"
    class="select-btn"
  >
    <span class="select-btn-name">{{ select.value }}</span>
    <svg
      :class="[select.isOpen ? '-rotate-180' : '']"
      class="select-btn-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
    >
      <path
        d="M233.4 406.6c12.5 12.5 32.8 12.5 45.3 0l192-192c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L256 338.7 86.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l192 192z"
      />
    </svg>
  </button>
  <div
    :id="`${select.id}-dropdown`"
    role="listbox"
    :style="{ width: selectWidth, top: selectTop }"
    :aria-hidden="select.isOpen ? 'false' : 'true'"
    :class="[select.isOpen ? 'flex' : 'hidden']"
    class="select-dropdown-container"
    :aria-description="$t('inp_select_dropdown_desc')"
  >
    <button
      role="option"
      :aria-controls="`${select.id}-option-${id}`"
      v-for="(value, id) in select.values"
      @click="
        () => {
          changeValue(value);
          // Case is same value as store on core
          if (value === select.valueStatic)
            return config.removeConf(
              props.serviceName || select.context,
              select.id,
              select.value,
              props.setting.regex,
            );

          // Case not same value as store on core
          return config.updateConf(
            props.serviceName || select.context,
            select.id,
            select.value,
            props.setting.regex,
          );
        }
      "
      :class="[
        id === 0 ? 'first' : '',
        id === select.values.length - 1 ? 'last' : '',
        value === select.value ? 'active' : '',
        'select-dropdown-btn',
      ]"
      :aria-description="$t('inp_select_option_desc')"
      :aria-selected="value === select.value ? 'true' : 'false'"
    >
      {{ value }}
    </button>
  </div>
</template>
