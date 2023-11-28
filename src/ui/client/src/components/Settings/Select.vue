<script setup>
import { ref, reactive, watch, onMounted, defineEmits, defineProps } from "vue";

const props = defineProps({
  // id && value && values && disabled
  settings: {
    type: Object,
    required: true,
  },
  inpClass: {
    type: String,
    required: false,
  },
});

// When mounted or when props changed, we want select to display new props values
// When component value change itself, we want to switch to select.value
// To avoid component to send and stick to props values (bad behavior)
// Trick is to use select.value || props.settings.value on template
watch(props, (newProp, oldProp) => {
  if (newProp.settings.value !== select.value) {
    select.value = "";
  }
});

const select = reactive({
  isOpen: false,
  // On mounted value is null to display props value
  // Then on new select we will switch to select.value
  // If we use select.value : props.settings.value
  // Component will not re-render after props.settings.value change
  value: "",
});

const selectBtn = ref();
const selectWidth = ref("");

// EVENTS
function toggleSelect() {
  select.isOpen = select.isOpen ? false : true;
}

function closeSelect() {
  select.isOpen = false;
}

function changeValue(newValue) {
  // Allow on template to switch from prop value to component own value
  // Then send the new value to parent
  select.value = newValue;
  closeSelect();
  return newValue;
}

// Close select dropdown when clicked outside element
watch(select, () => {
  if (select.isOpen) {
    document.querySelector("body").addEventListener("click", closeOutside);
  } else {
    document.querySelector("body").removeEventListener("click", closeOutside);
  }
});

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

onMounted(() => {
  selectWidth.value = `${selectBtn.value.clientWidth}px`;
  window.addEventListener("resize", () => {
    try {
      selectWidth.value = `${selectBtn.value.clientWidth}px`;
    } catch (err) {}
  });
});

const emits = defineEmits(["inp"]);
</script>

<template>
  <!-- default hidden-->
  <select
    :id="props.settings.id"
    :name="props.settings.id"
    :aria-description="$t('inp_select_default_desc')"
    class="hidden"
  >
    <option
      v-for="value in props.settings.values"
      :value="value"
      :selected="value === props.settings.value ? true : false"
    >
      {{ value }}
    </option>
  </select>
  <!-- end default hidden-->

  <!--custom-->
  <div class="relative">
    <button
      ref="selectBtn"
      :aria-description="$t('inp_select_dropdown_button_desc')"
      data-select-dropdown
      :disabled="props.settings.disabled || false"
      :aria-expanded="select.isOpen ? 'true' : 'false'"
      @click="toggleSelect()"
      :class="['select-btn', props.inpClass]"
    >
      <span class="select-btn-name">
        {{ select.value || props.settings.value }}
      </span>
      <!-- chevron -->
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
      <!-- end chevron -->
    </button>
    <!-- dropdown-->
    <div
      :style="{ width: selectWidth }"
      :aria-hidden="select.isOpen ? 'false' : 'true'"
      :class="[select.isOpen ? 'flex' : 'hidden']"
      class="select-dropdown-container"
      :aria-description="$t('inp_select_dropdown_desc')"
    >
      <button
        v-for="(value, id) in props.settings.values"
        @click="$emit('inp', changeValue(value))"
        :class="[
          id === 0 ? 'first' : '',
          id === props.settings.values.length - 1 ? 'last' : '',
          value === props.settings.value ? 'active' : '',
          'select-dropdown-btn',
        ]"
        :aria-description="$t('inp_select_option_desc')"
        :aria-current="value === props.settings.value ? 'true' : 'false'"
      >
        {{ value }}
      </button>
    </div>
    <!-- end dropdown-->
  </div>
  <!-- end custom-->
</template>
