<script setup>
import {
  ref,
  reactive,
  watch,
  onMounted,
  defineEmits,
  defineProps,
  computed,
  onBeforeMount,
} from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";
import ErrorDropdown from "@components/Forms/Error/Dropdown.vue";
import { useUUID } from "@utils/global.js";

/**
  @name Forms/Field/Combobox.vue
  @description This component is used to create a complete combobox field input with error handling and label.
  We can be more precise by adding values that need to be selected to be valid.
  We can also add popover to display more information.
  @example
  {
    id: 'test-input',
    value: 'yes',
    values : ['yes', 'no'],
    name: 'test-input',
    disabled: false,
    required: true,
    requiredValues : ['no'], // need required to be checked
    label: 'Test select',
    inpType: "select",
    popovers : [
      {
        text: "This is a popover text",
        iconName: "info",
      },]
  }
  @param {string} [id=uuidv4()] - Unique id
  @param {string} label - The label of the field. Can be a translation key or by default raw text.
  @param {string} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
  @param {string} value
  @param {array} values
  @param {object} [attrs={}] - Additional attributes to add to the field
  @param {string} [maxBtnChars=""] - Max char to display in the dropdown button handler.
  @param {array} [popovers] - List of popovers to display more information
  @param {string} [inpType="select"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
  @param {boolean} [disabled=false]
  @param {boolean} [required=false]
  @param {array} [requiredValues=[]] - values that need to be selected to be valid, works only if required is true
  @param {object} [columns={"pc": "12", "tablet": "12", "mobile": "12}] - Field has a grid system. This allow to get multiple field in the same row if needed.
  @param {boolean} [hideLabel=false]
  @param {boolean} [onlyDown=false] - If the dropdown should check the bottom of the 
    @param {boolean} [overflowAttrEl=""] - Attribut to select the container the element has to check for overflow
  @param {string} [containerClass=""]
  @param {string} [inpClass=""]
  @param {string} [headerClass=""]
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const props = defineProps({
  // id && value && method
  id: {
    type: String,
    required: false,
    default: "",
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: false,
  },
  value: {
    type: String,
    required: true,
  },
  values: {
    type: Array,
    required: true,
    default: [],
  },
  attrs: {
    type: Object,
    required: false,
    default: {},
  },
  maxBtnChars: {
    type: [String, Number],
    required: false,
    default: "",
  },
  inpType: {
    type: String,
    required: false,
    default: "select",
  },
  disabled: {
    type: Boolean,
    required: false,
  },
  required: {
    type: Boolean,
    required: false,
  },
  requiredValues: {
    type: Array,
    required: false,
    default: [],
  },
  label: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  popovers: {
    type: Array,
    required: false,
    default: [],
  },
  hideLabel: {
    type: Boolean,
    required: false,
  },
  onlyDown: {
    type: Boolean,
    required: false,
    default: false,
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  overflowAttrEl: {
    type: String,
    required: false,
    default: "",
  },
  headerClass: {
    type: String,
    required: false,
    default: "",
  },
  inpClass: {
    type: String,
    required: false,
    default: "",
  },
  tabId: {
    type: [String, Number],
    required: false,
    default: contentIndex,
  },
});

// Case we have another value set from the parent for any reason
// (like a filter that removed some values or forced a value)
watch(
  () => props.value,
  () => {
    select.value = props.value;
  }
);
const inp = reactive({
  id: "",
  value: "",
  isValid: true,
  isMatching: computed(() => {
    if (!props.values) return false;
    return props.values.some((str) =>
      str.toLowerCase().includes(inp.value.toLowerCase())
    );
  }),
});

const inputEl = ref();

const select = reactive({
  isOpen: false,
  // On mounted value is null to display props value
  // Then on new select we will switch to select.value
  // If we use select.value : props.value
  // Component will not re-render after props.value change
  value: "",
  isValid: !props.required
    ? true
    : props.requiredValues.length <= 0
    ? true
    : props.requiredValues.includes(props.value)
    ? true
    : false,
});

const selectBtn = ref();
const selectWidth = ref("");
const selectDropdown = ref();

/**
  @name toggleSelect
  @description This will toggle the custom select dropdown component.
  @returns {void}
*/
function toggleSelect() {
  select.isOpen = select.isOpen ? false : true;
  // Position dropdown relative to btn on open on fixed position
  if (select.isOpen) {
    // Reset input value
    inp.value = "";
    inputEl.value.focus();

    setTimeout(() => {
      // Get field container rect
      const fieldContainer = selectBtn.value.closest("[data-field-container]");
      const parent = props.overflowAttrEl
        ? fieldContainer.closest(`[${props.overflowAttrEl}]`)
        : fieldContainer.parentElement;
      // Update position only if parent has overflow
      const isOverflow =
        parent.scrollHeight > parent.clientHeight ? true : false;
      if (!isOverflow) return;

      // Get all rect
      const selectBtnRect = selectBtn.value.getBoundingClientRect();
      const fieldContainerRect = fieldContainer.getBoundingClientRect();
      const selectDropRect = selectDropdown.value.getBoundingClientRect();

      const parentRect = parent.getBoundingClientRect();

      const canBeDown = props.onlyDown
        ? true
        : fieldContainerRect.bottom + selectDropRect.height < parentRect.bottom
        ? true
        : false;

      if (!canBeDown) {
        selectDropdown.value.style.top = `-${
          selectDropRect.height + selectBtnRect.height - 16
        }px`;
      }

      if (canBeDown) {
        selectDropdown.value.style.top = `${selectBtnRect.height}px`;
      }
    }, 10);
  }
}

/**
  @name closeSelect
  @description This will close the custom select dropdown component.
  @returns {void}
*/
function closeSelect() {
  select.isOpen = false;
}

/**
  @name changeValue
  @description This will change the value of the select when a new value is selected from dropdown button.
  Check the validity of the select too. Close select after it.
  @param {string} newValue - The new value to set to the select.
  @returns {string} - The new value of the select
*/
function changeValue(newValue) {
  // Allow on template to switch from prop value to component own value
  // Then send the new value to parent
  select.value = newValue;
  // Check if value is required and if it is in requiredValues
  select.isValid = !props.required
    ? true
    : props.requiredValues.length <= 0
    ? true
    : props.requiredValues.includes(newValue)
    ? true
    : false;
  closeSelect();
  return newValue;
}

/**
  @name closeOutside
  @description This function is linked to a click event and will check if the target is part of the select component.
  Case not and select is open, will close the select.
  @param {event} e - The event object.
  @returns {void}
*/
function closeOutside(e) {
  try {
    if (e.target !== selectBtn.value && e.target !== inputEl.value) {
      select.isOpen = false;
    }
  } catch (err) {
    select.isOpen = false;
  }
}

/**
  @name closeScroll
  @description This function is linked to a scroll event and will close the select in case a scroll is detected and the scroll is not the dropdown.
  @param {event} e - The event object.
  @returns {void}
*/
function closeScroll(e) {
  if (!e.target) return;
  // Case not a DOM element (like the document itself)
  if (e.target.nodeType !== 1) return (select.isOpen = false);
  // Case DOM, check if it is the select dropdown
  if (
    e.target.hasAttribute("data-select-dropdown") ||
    e.target.hasAttribute("data-select-dropdown-items")
  )
    return;
  select.isOpen = false;
}

/**
  @name closeEscape
  @description This function is linked to a key event and will close the select in case "Escape" key is pressed.
  @param {event} e - The event object.
  @returns {void}
*/
function closeEscape(e) {
  if (e.key !== "Escape") return;
  select.isOpen = false;
}

/**
  @name closeTab
  @description This function is linked to a key event and will listen to tabindex change.
  In case the new tabindex is not part of the select component, will close the select.
  @param {event} e - The event object.
  @returns {void}
*/
function closeTab(e) {
  if (e.key !== "Tab" && e.key !== "Shift-Tab") return;
  setTimeout(() => {
    const activeEl = document.activeElement;
    if (activeEl.closest("[data-select-dropdown]") !== selectDropdown.value)
      return (select.isOpen = false);
  }, 10);
}

// Close select dropdown when clicked outside element
watch(select, () => {
  if (select.isOpen) {
    inputEl.value.focus();
    window.addEventListener("scroll", closeScroll, true);
    window.addEventListener("click", closeOutside);
    window.addEventListener("keydown", closeTab);
    window.addEventListener("keydown", closeEscape);
  } else {
    window.removeEventListener("scroll", closeScroll, true);
    window.removeEventListener("click", closeOutside);
    window.removeEventListener("keydown", closeTab);
    window.removeEventListener("keydown", closeEscape);
  }
});

onBeforeMount(() => {
  inp.id = useUUID(props.id);
});

onMounted(() => {
  inp.isValid = inputEl.value.checkValidity();
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
  <Container
    data-field-container
    :class="[select.isOpen ? 'z-[100]' : '']"
    :containerClass="`${props.containerClass}`"
    :columns="props.columns"
  >
    <Header
      :popovers="props.popovers"
      :required="props.required"
      :name="props.name"
      :id="inp.id"
      :label="props.label"
      :hideLabel="props.hideLabel"
      :headerClass="props.headerClass"
    />

    <select :id="inp.id" aria-hidden="true" :name="props.name" class="hidden">
      <option
        v-for="(value, id) in props.values"
        :key="id"
        :value="value"
        @click="$emit('inp', changeValue(value))"
        :selected="
          (select.value && select.value === value) ||
          (!select.value && value === props.value)
            ? true
            : false
        "
      >
        {{ value }}
      </option>
    </select>
    <!-- end default select -->

    <!--custom-->
    <div class="relative">
      <button
        v-bind="props.attrs"
        data-toggle-dropdown
        :name="`${props.name}-custom`"
        :tabindex="props.tabId"
        ref="selectBtn"
        :aria-controls="`${inp.id}-custom`"
        :aria-expanded="select.isOpen ? 'true' : 'false'"
        :aria-description="$t('inp_select_dropdown_button_desc')"
        :disabled="props.disabled || false"
        @click.prevent="toggleSelect()"
        :class="[
          'select-btn',
          select.isValid ? 'valid' : 'invalid',
          props.inpClass,
        ]"
      >
        <span :id="`${inp.id}-text`" class="select-btn-name">
          {{
            props.maxBtnChars &&
            (select.value || props.value).length > +props.maxBtnChars
              ? `${
                  select.value.substring(0, props.maxBtnChars) ||
                  props.value.substring(0, props.maxBtnChars)
                }...`
              : select.value || props.value
          }}
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
        data-select-dropdown
        ref="selectDropdown"
        :style="{ width: selectWidth }"
        :id="`${inp.id}-custom`"
        :class="[select.isOpen ? 'open' : 'close']"
        class="select-dropdown-container"
        :aria-hidden="select.isOpen ? 'false' : 'true'"
        role="combobox"
        :aria-expanded="select.isOpen ? 'true' : 'false'"
        :aria-description="$t('inp_select_dropdown_desc')"
      >
        <div>
          <label :class="['sr-only']" :for="`${inp.id}-combobox`">
            {{ $t("inp_combobox") }}
          </label>
          <input
            :tabindex="select.isOpen ? props.tabId : '-1'"
            ref="inputEl"
            v-model="inp.value"
            :placeholder="$t('inp_combobox_placeholder')"
            @input="inp.isValid = inputEl.checkValidity()"
            :aria-controls="`${inp.id}-list`"
            :id="`${inp.id}-combobox`"
            :class="[
              'input-combobox',
              inp.isValid ? 'valid' : 'invalid',
              props.inpClass,
            ]"
            :pattern="props.pattern || '(?s).*'"
            :name="`${inp.id}-combobox`"
            :value="inp.value"
            :type="'text'"
          />
          <ErrorDropdown
            v-if="!inp.isMatching"
            :isNoMatch="true"
            :isValid="false"
          />
        </div>
        <div
          v-if="inp.isMatching"
          data-select-dropdown-items
          :id="`${inp.id}-list`"
          :aria-hidden="select.isOpen ? 'false' : 'true'"
          role="radiogroup"
          class="select-combobox-list"
        >
          <template v-for="(value, id) in props.values">
            <button
              v-if="value.toLowerCase().includes(inp.value.toLowerCase())"
              :aria-hidden="
                value.toLowerCase().includes(inp.value.toLowerCase())
                  ? 'false'
                  : 'true'
              "
              :tabindex="
                select.isOpen
                  ? value.toLowerCase().includes(inp.value.toLowerCase())
                    ? props.tabId
                    : '-1'
                  : '-1'
              "
              role="radio"
              @click.prevent="$emit('inp', changeValue(value))"
              :class="[
                (value === select.value && select.value === value) ||
                (!select.value && value === props.value)
                  ? 'active'
                  : '',
                'select-dropdown-btn',
              ]"
              data-select-item
              :data-setting-id="inp.id"
              :data-setting-value="value"
              :aria-controls="`${inp.id}-text`"
              :aria-checked="
                (select.value && select.value === value) ||
                (!select.value && value === props.value)
                  ? 'true'
                  : 'false'
              "
            >
              {{ value }}
            </button>
          </template>
        </div>
      </div>
      <ErrorField
        :errorClass="'combobox'"
        :isValid="select.isValid"
        :isValue="true"
      />
      <!-- end dropdown-->
    </div>
    <!-- end custom-->
  </Container>
</template>
