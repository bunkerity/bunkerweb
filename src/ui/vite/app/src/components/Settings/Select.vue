<script setup>
import { ref, reactive, watch, onMounted, defineEmits, defineProps } from "vue";

const props = defineProps({
  settings: {
    type: Object,
    required: true,
  },
});

const select = reactive({
  id: props.settings.id,
  values: props.settings.values,
  value: props.settings.value,
  isOpen: false,
  disabled: props.settings.disabled || false,
});

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
  return select.value;
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
    if (!e.target.closest("button").hasAttribute("data-select-dropdown")) {
      select.isOpen = false;
    }
  } catch (err) {
    select.isOpen = false;
  }
}

const selectBtn = ref();
const selectWidth = ref("");

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
    :id="select.id"
    :name="select.id"
    aria-description="Communicate with a custom visible select."
    class="hidden"
  >
    <option
      v-for="value in select.values"
      :value="value"
      :selected="value === select.value ? true : false"
    >
      {{ value }}
    </option>
  </select>
  <!-- end default hidden-->

  <!--custom-->
  <div class="relative">
    <button
      ref="selectBtn"
      aria-description="custom select dropdown button"
      data-select-dropdown
      :disabled="select.disabled"
      :aria-expanded="select.isOpen ? 'true' : 'false'"
      @click="toggleSelect()"
      class="select-btn"
    >
      <span>{{ select.value }}</span>
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
      aria-description="custom select dropdown"
    >
      <button
        v-for="(value, id) in select.values"
        @click="$emit('inp', changeValue(value))"
        :class="[
          id === 0 ? 'first' : '',
          id === select.values.length - 1 ? 'last' : '',
          value === select.value ? 'active' : '',
          'select-dropdown-btn',
        ]"
        aria-description="custom select option"
        :aria-current="value === select.value ? 'true' : 'false'"
      >
        {{ value }}
      </button>
    </div>
    <!-- end dropdown-->
  </div>
  <!-- end custom-->
</template>
