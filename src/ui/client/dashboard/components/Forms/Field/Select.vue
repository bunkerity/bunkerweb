<script setup>
import {
  ref,
  reactive,
  watch,
  onMounted,
  defineEmits,
  defineProps,
  onBeforeMount,
} from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";
import { useUUID } from "@utils/global";

/**
 *  @name Forms/Field/Select.vue
 *  @description This component is used to create a complete select field input with error handling and label.
 *  We can be more precise by adding values that need to be selected to be valid.
 *  We can also add popover to display more information.
 *  It is mainly use in forms.
 *  @example
 *  {
 *    id: 'test-input',
 *    value: 'yes',
 *    values : ['yes', 'no'],
 *    name: 'test-input',
 *    disabled: false,
 *    required: true,
 *    requiredValues : ['no'], // need required to be checked
 *    label: 'Test select',
 *    inpType: "select",
 *    popovers : [
 *      {
 *        text: "This is a popover text",
 *        iconName: "info",
 *      },
 *    ]
 *  }
 *  @param {String} [id=uuidv4()] - Unique id
 *  @param {String} label - The label of the field. Can be a translation key or by default raw text.
 *  @param {String} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
 *  @param {String} value
 *  @param {Array} values
 *  @param {Object} [attrs={}] - Additional attributes to add to the field
 *  @param {Array} [popovers=[]] - List of popovers to display more information
 *  @param {String} [inpType="select"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
 *  @param {String} [maxBtnChars=""] - Max char to display in the dropdown button handler.
 *  @param {Boolean} [disabled=false]
 *  @param {Boolean} [required=false]
 *  @param {Array} [requiredValues=[]] - values that need to be selected to be valid, works only if required is true
 *  @param {Object} [columns={"pc": "12", "tablet": "12", "mobile": "12"}] - Field has a grid system. This allow to get multiple field in the same row if needed.
 *  @param {Boolean} [hideLabel=false]
 *  @param {Boolean} [onlyDown=false] - If the dropdown should check the bottom of the container
 *  @param {Boolean} [overflowAttrEl=""] - Attribute to select the container the element has to check for overflow
 *  @param {String} [containerClass=""]
 *  @param {String} [inpClass=""]
 *  @param {String} [headerClass=""]
 *  @param {String} [fieldSize="normal"] - Size between "normal" or "sm"
 *  @param {String|Number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
 */

const props = defineProps({
  // id && value && method
  id: {
    type: String,
    required: false,
    default: "",
  },
  fieldSize: {
    type: String,
    required: false,
    default: "normal",
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
  },
  attrs: {
    type: Object,
    required: false,
    default: {},
  },
  inpType: {
    type: String,
    required: false,
    default: "select",
  },
  maxBtnChars: {
    type: [String, Number],
    required: false,
    default: "",
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
  required: {
    type: Boolean,
    required: false,
    default: false,
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
  onlyDown: {
    type: Boolean,
    required: false,
    default: false,
  },
  overflowAttrEl: {
    type: String,
    required: false,
    default: "",
  },
  hideLabel: {
    type: Boolean,
    required: false,
    default: false,
  },
  containerClass: {
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

const select = reactive({
  id: "",
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
 *  @name toggleSelect
 *  @description This will toggle the custom select dropdown component.
 *  @returns {Void}
 */
function toggleSelect() {
  select.isOpen = select.isOpen ? false : true;
  // Check if parent has overflow
  if (select.isOpen) {
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
 *  @name closeSelect
 *  @description This will close the custom select dropdown component.
 *  @returns {Void}
 */
function closeSelect() {
  select.isOpen = false;
}

/**
*  @name changeValue
*  @description This will change the value of the select when a new value is selected from dropdown button.
  Check the validity of the select too. Close select after it.
*  @param {string} newValue - The new value to set to the select.
*  @returns {string} - The new value of the select
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
 *  @name closeOutside
 *  @description This function is linked to a click event and will check if the target is part of the select component.
 *  Case not and select is open, will close the select.
 *  @param {Event} e - The event object.
 *  @returns {Void}
 */
function closeOutside(e) {
  try {
    if (e.target !== selectBtn.value) {
      select.isOpen = false;
    }
  } catch (err) {
    select.isOpen = false;
  }
}

/**
 *  @name closeScroll
 *  @description This function is linked to a scroll event and will close the select in case a scroll is detected and the scroll is not the dropdown.
 *  @param {Event} e - The event object.
 *  @returns {Void}
 */
function closeScroll(e) {
  if (!e.target) return;
  // Case not a DOM element (like the document itself)
  if (e.target.nodeType !== 1) return (select.isOpen = false);
  // Case DOM, check if it is the select dropdown
  if (e.target.hasAttribute("data-select-dropdown")) return;
  select.isOpen = false;
}

/**
 *  @name closeEscape
 *  @description This function is linked to a key event and will close the select in case "Escape" key is pressed.
 *  @param {Event} e - The event object.
 *  @returns {Void}
 */

function closeEscape(e) {
  if (e.key !== "Escape") return;
  select.isOpen = false;
}

/**
 *  @name closeTab
 *  @description This function is linked to a key event and will listen to tabindex change.
 *  In case the new tabindex is not part of the select component, will close the select.
 *  @param {Event} e - The event object.
 *  @returns {Void}
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
  select.id = useUUID(props.id);
});

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
  <Container
    :class="[select.isOpen ? 'z-[100]' : '']"
    data-field-container
    :containerClass="`${props.containerClass}`"
    :columns="props.columns"
  >
    <Header
      :popovers="props.popovers"
      :required="props.required"
      :name="props.name"
      :label="props.label"
      :id="select.id"
      :hideLabel="props.hideLabel"
      :headerClass="props.headerClass"
      :fieldSize="props.fieldSize"
    />

    <select :id="select.id" :name="props.name" class="hidden">
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
        :name="`${props.name}-custom`"
        :tabindex="props.tabId"
        ref="selectBtn"
        :aria-controls="`${select.id}-custom`"
        :aria-expanded="select.isOpen ? 'true' : 'false'"
        :aria-description="$t('inp_select_dropdown_button_desc')"
        data-select-dropdown
        :disabled="props.disabled || false"
        @click.prevent="toggleSelect()"
        :class="[
          'select-btn',
          select.isValid ? 'valid' : 'invalid',
          props.inpClass,
          props.fieldSize,
        ]"
      >
        <span :id="`${select.id}-text`" class="select-btn-name">
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
        :aria-hidden="select.isOpen ? 'false' : 'true'"
        :aria-expanded="select.isOpen ? 'true' : 'false'"
        ref="selectDropdown"
        role="radiogroup"
        :style="{ width: selectWidth }"
        :id="`${select.id}-custom`"
        :class="[select.isOpen ? 'open' : 'close']"
        class="select-dropdown-container"
        :aria-description="$t('inp_select_dropdown_desc')"
      >
        <button
          :tabindex="select.isOpen ? props.tabId : '-1'"
          v-for="(value, id) in props.values"
          role="radio"
          @click.prevent="$emit('inp', changeValue(value))"
          :class="[
            id === 0 ? 'first' : '',
            id === props.values.length - 1 ? 'last' : '',
            (value === select.value && select.value === value) ||
            (!select.value && value === props.value)
              ? 'active'
              : '',
            'select-dropdown-btn',
            props.fieldSize,
          ]"
          data-select-item
          :data-setting-id="select.id"
          :data-setting-value="value"
          :aria-controls="`${select.id}-text`"
          :aria-checked="
            (select.value && select.value === value) ||
            (!select.value && value === props.value)
              ? 'true'
              : 'false'
          "
        >
          {{ value }}
        </button>
      </div>
      <ErrorField
        :errorClass="'select'"
        :isValid="select.isValid"
        :isValue="true"
      />
      <!-- end dropdown-->
    </div>
    <!-- end custom-->
  </Container>
</template>
