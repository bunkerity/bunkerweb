<script setup>
import { ref, reactive, watch, onMounted, defineEmits, defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Base from "@components/Forms/Field/Base.vue";
import Header from "@components/Forms/Header/Field.vue";


/* PROPS ARGUMENTS
  *
  *
  id: string,
  value:  string,
  values:  array,
  disabled: boolean,
  required: boolean,
  label: string,
  name: string,
  version: string,
  hideLabel: boolean,
  inpClass: string,
  headerClass: string,
  tabId: string || number,
  *
  *
*/


const props = defineProps({
  // id && value && method
    id: {
        type: String,
        required: true,
    },
    value: {
        type: String,
        required: true,
    },
    values: {
        type: Array,
        required: true,
    },
    disabled: {
        type: Boolean,
        required: false,
    },
    required: {
        type: Boolean,
        required: false,
    },
    label: {
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
    },
    hideLabel: {
        type: Boolean,
        required: false,
    },
    headerClass: {
        type: String,
        required: false,
    },
    inpClass: {
        type: String,
        required: false,
    },
    tabId: {
        type: [String, Number],
        required: false,
    },
});


// When mounted or when props changed, we want select to display new props values
// When component value change itself, we want to switch to select.value
// To avoid component to send and stick to props values (bad behavior)
// Trick is to use select.value || props.value on template
watch(props, (newProp, oldProp) => {
  if (newProp.value !== select.value) {
    select.value = "";
  }
});

const select = reactive({
  isOpen: false,
  // On mounted value is null to display props value
  // Then on new select we will switch to select.value
  // If we use select.value : props.value
  // Component will not re-render after props.value change
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
  <Base>
    <Header :required="props.required" :name="props.name" :label="props.label" :hideLabel="props.hideLabel" :headerClass="props.headerClass" />

<select :name="props.name" class="hidden">
  <option
    v-for="(value, id) in props.values"
    :key="id"
    :value="value"
    @click="$emit('inp', changeValue(value))"
    :selected="select.value && select.value === value || !select.value && value === props.value ? true : false"
  >
    {{ value }}
  </option>
</select>
<!-- end default select -->

<!--custom-->
<div class="relative">
  <button
    :name="`${props.name}-custom`"	
    :tabindex="props.tabId || contentIndex"
    ref="selectBtn"
    :aria-controls="`${props.id}-custom`"
    :aria-expanded="select.isOpen ? 'true' : 'false'"
    :aria-description="$t('inp_select_dropdown_button_desc')"
    data-select-dropdown
    :disabled="props.disabled || false"
    @click="toggleSelect()"
    :class="['select-btn', props.inpClass]"
  >
    <span :id="`${props.id}-text`" class="select-btn-name">
      {{ select.value || props.value }}
    </span>
    <!-- chevron -->
    <svg
      role="img"
      aria-hidden="true"
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
    role="radiogroup"
    :style="{ width: selectWidth }"
    :id="`${props.id}-custom`"
    :class="[select.isOpen ? 'flex' : 'hidden']"
    class="select-dropdown-container"
    :aria-description="$t('inp_select_dropdown_desc')"
  >
    <button
      :tabindex="contentIndex"
      v-for="(value, id) in props.values"
      role="radio"
      @click="$emit('inp', changeValue(value))"
      :class="[
        id === 0 ? 'first' : '',
        id === props.values.length - 1 ? 'last' : '',
        value === select.value && select.value === value || !select.value && value === props.value ? 'active' : '',
        'select-dropdown-btn',
      ]"
      :aria-controls="`${props.id}-text`"
      :aria-checked="select.value && select.value === value || !select.value && value === props.value ? 'true' : 'false'"
    >
      {{ value }}
    </button>
  </div>
  <!-- end dropdown-->
</div>
<!-- end custom-->
  </Base>
 
</template>