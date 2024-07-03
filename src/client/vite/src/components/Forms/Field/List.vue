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
import { useUUID } from "@utils/global.js";
import Icons from "@components/Widget/Icons.vue";
import ErrorDropdown from "@components/Forms/Error/Dropdown.vue";

/**
  @name Forms/Field/List.vue
  @description This component is used display list of values in a dropdown, remove or add an item in an easy way.
  We can also add popover to display more information.
  @example
  {
    id: 'test-input',
    value: 'yes no maybe',
    name: 'test-list',
    label: 'Test list',
    inpType: "list",
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
  @param {string} [separator=" "] - Separator to split the value, by default it is a space
  @param {string} [maxBtnChars=""] - Max char to display in the dropdown button handler.
  @param {array} [popovers] - List of popovers to display more information
  @param {string} [inpType="list"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
  @param {boolean} [disabled=false]
  @param {boolean} [required=false]
  @param {object} [columns={"pc": "12", "tablet": "12", "mobile": "12}] - Field has a grid system. This allow to get multiple field in the same row if needed.
  @param {boolean} [hideLabel=false]
  @param {boolean} [onlyDown=false] - If the dropdown should stay down 
  @param {boolean} [overflowAttrEl=""] - Attribute the element has to check for overflow
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
  separator: {
    type: String,
    required: false,
    default: " ",
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

const inp = reactive({
  isOpen: false,
  id: "",
  value: props.value,
  values: computed(() => {
    return inp.value.split(props.separator);
  }),
  isValid: computed(() => {
    // Case enter value start or en by separator
    if (inp.value.startsWith(props.separator)) return false;
    if (inp.value.endsWith(props.separator)) return false;
    if (!inp.value && props.required) return false;
    if (!props.pattern) return true;
    // Check if value is valid related to pattern
    return inp.value.match(new RegExp(props.pattern)) ? true : false;
  }),
  enterValue: "",
  // Check if enter value is already a value
  isEnterMatching: computed(() => {
    if (!inp.enterValue) return false;
    if (!props.value.split(props.separator)) return false;
    return props.value
      .split(props.separator)
      .some((str) => str.toLowerCase() === inp.enterValue.toLowerCase());
  }),
  // Check that the current inp.value with the current enter value is valid related to pattern
  isEnterValid: computed(() => {
    // Case enter value start or en by separator
    if (inp.enterValue.startsWith(props.separator)) return false;
    if (inp.enterValue.endsWith(props.separator)) return false;
    if (!inp.enterValue) return true;
    if (!props.required) return true;
    if (!props.pattern) return true;

    const newValue = inp.enterValue
      ? `${inp.value} ${inp.enterValue}`
      : inp.value;
    return newValue.match(new RegExp(props.pattern)) ? true : false;
  }),
});

const inputEl = ref();
const selectWidth = ref("");
const selectDropdown = ref();

// EVENTS
function openSelect() {
  inp.isOpen = true;
  // Reset input value
  setTimeout(() => {
    // Get field container rect
    const fieldContainer = inputEl.value.closest("[data-field-container]");
    const parent = props.overflowAttrEl
      ? fieldContainer.closest(`[${props.overflowAttrEl}]`)
      : fieldContainer.parentElement;
    // Update position only if parent has overflow
    const isOverflow = parent.scrollHeight > parent.clientHeight ? true : false;
    if (!isOverflow) return;

    // Get all rect
    const selectBtnRect = inputEl.value.getBoundingClientRect();
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

// Close select when clicked outside logic
function closeOutside(e) {
  if (
    e.target.hasAttribute("data-select-item") ||
    e.target.hasAttribute("data-delete-entry")
  )
    return;
  try {
    if (e.target !== inputEl.value && e.target !== inputEl.value) {
      inp.isOpen = false;
    }
  } catch (err) {
    inp.isOpen = false;
  }
}

function closeScroll(e) {
  if (!e.target) return;
  // Case not a DOM element (like the document itself)
  if (e.target.nodeType !== 1) return (inp.isOpen = false);
  // Case DOM, check if it is the select dropdown
  if (
    e.target.hasAttribute("data-select-dropdown") ||
    e.target.hasAttribute("data-select-dropdown-items")
  )
    return;
  inp.isOpen = false;
}

function closeEscape(e) {
  if (e.key !== "Escape") return;
  inp.isOpen = false;
}

// Check after a key is pressed if the current active element is the select button
// If not close the select
function closeTab(e) {
  if (e.key !== "Tab" && e.key !== "Shift-Tab") return;
  setTimeout(() => {
    const activeEl = document.activeElement;
    if (
      activeEl.closest("[data-select-dropdown]") !== selectDropdown.value &&
      activeEl
        ?.closest("[data-input-container]")
        ?.querySelector("[data-toggle-dropdown]") !== inputEl.value
    )
      return (inp.isOpen = false);
  }, 10);
}

// Case the entry is focus and value is valid, add it to the list
function addEntry(e) {
  // check if keyboard event
  if (e.key && e.key !== "Enter") return;
  if (!inp.isEnterValid || inp.isEnterMatching) return;
  if (
    document.activeElement !== inputEl.value &&
    !e.target.hasAttribute("data-add-entry")
  )
    return;

  inp.value = `${inp.enterValue}${props.separator}${inp.value}`.trim();
  inp.enterValue = "";
  inputEl.value.focus();
}

// Case the entry is focus and value is valid, add it to the list
function deleteValue(value) {
  inp.value = inp.value
    .split(props.separator)
    .filter((val) => val !== value)
    .join(props.separator)
    .trim();

  // Case no item anymore, focus on main input
  if (!inp.value) inputEl.value.focus();
}

// Close select dropdown when clicked outside element
watch(inp, () => {
  if (inp.isOpen) {
    window.addEventListener("scroll", closeScroll, true);
    window.addEventListener("click", closeOutside);
    window.addEventListener("keydown", closeEscape);
    window.addEventListener("keydown", closeTab);
    window.addEventListener("keydown", addEntry);
  } else {
    window.removeEventListener("scroll", closeScroll, true);
    window.removeEventListener("click", closeOutside);
    window.removeEventListener("keydown", closeEscape);
    window.removeEventListener("keydown", closeTab);
    window.removeEventListener("keydown", addEntry);
  }
});

onBeforeMount(() => {
  inp.id = useUUID(props.id);
});

onMounted(() => {
  selectWidth.value = `${inputEl.value.clientWidth}px`;
  window.addEventListener("resize", () => {
    try {
      selectWidth.value = `${inputEl.value.clientWidth}px`;
    } catch (err) {}
  });
});

const emits = defineEmits(["inp"]);
</script>

<template>
  <Container
    data-field-container
    :class="[inp.isOpen ? 'z-[100]' : '']"
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

    <!--custom-->
    <div class="relative">
      <div data-input-container class="input-regular-container">
        <input
          data-toggle-dropdown
          :aria-controls="`${inp.id}-custom`"
          :aria-expanded="inp.isOpen ? 'true' : 'false'"
          :aria-description="$t('inp_list_input_desc')"
          :tabindex="props.tabId"
          ref="inputEl"
          @input="
            (e) => {
              openSelect();
              inp.enterValue = e.target.value;
              $emit('inp', inp.value);
            }
          "
          :id="inp.id"
          :class="[
            'input-regular',
            inp.isValid && !inp.isEnterMatching && inp.isEnterValid
              ? 'valid'
              : 'invalid',
            props.inpClass,
          ]"
          @focusin="openSelect()"
          :required="props.required || false"
          :readonly="props.readonly || false"
          :disabled="props.disabled || false"
          :placeholder="
            props.placeholder
              ? $t(
                  props.placeholder,
                  $t('dashboard_placeholder', props.placeholder)
                )
              : ''
          "
          :name="props.name"
          :value="inp.enterValue"
          type="text"
        />
        <button
          :tabindex="props.tabId"
          data-add-entry
          @click.prevent="(e) => addEntry(e)"
          :disabled="
            inp.isValid &&
            !inp.isEnterMatching &&
            inp.isEnterValid &&
            inp.enterValue
              ? false
              : true
          "
          :data-is="'input'"
          class="input-list-add"
        >
          <Icons :iconName="'plus'" />
        </button>
        <svg
          role="img"
          aria-hidden="true"
          :class="[inp.isOpen ? '-rotate-180' : '']"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.5"
          stroke="currentColor"
          class="input-list-svg"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12"
          />
        </svg>
      </div>
      <!-- dropdown-->
      <ul
        data-select-dropdown
        :aria-hidden="inp.isOpen ? 'false' : 'true'"
        :aria-expanded="inp.isOpen ? 'true' : 'false'"
        ref="selectDropdown"
        :style="{ width: selectWidth }"
        :id="`${inp.id}-custom`"
        :class="[inp.isOpen ? 'open' : 'close']"
        class="list-dropdown-container"
        :aria-description="$t('inp_select_dropdown_desc')"
      >
        <ErrorDropdown
          v-if="!inp.isMatching || !inp.isEnterValid || !inp.isValid"
          :isValid="inp.isValid && !inp.isEnterMatching && inp.isEnterValid"
          :isValue="props.required ? !!inp.value : true"
          :isValueTaken="inp.isEnterMatching"
        />
        <template
          v-if="
            inp.isValid &&
            !inp.isEnterMatching &&
            inp.isEnterValid &&
            inp.values.length >= 0 &&
            inp.values[0]
          "
        >
          <li
            :tabindex="inp.isOpen ? props.tabId : '-1'"
            v-for="(value, id) in inp.values"
            :class="[
              id === 0 ? 'first' : '',
              id === inp.values.length - 1 ? 'last' : '',
              'list-dropdown-btn',
            ]"
            data-select-item
            :data-setting-id="inp.id"
            :data-setting-value="value"
            :aria-controls="`${inp.id}-text`"
          >
            <span>
              {{ value }}
            </span>
            <button
              data-delete-entry
              :tabindex="inp.isOpen ? props.tabId : '-1'"
              data-is="input"
              @click="deleteValue(value)"
            >
              <Icons :iconName="'trash'" />
            </button>
          </li>
        </template>
      </ul>
      <ErrorField
        :errorClass="'input'"
        v-if="
          (!inp.isOpen && !inp.isMatching) ||
          (!inp.isOpen && !inp.isEnterValid) ||
          (!inp.isOpen && !inp.isValid)
        "
        :isValid="inp.isValid && !inp.isEnterMatching && inp.isEnterValid"
        :isValue="props.required ? !!inp.value : true"
        :isValueTaken="inp.isEnterMatching"
      />
      <!-- end dropdown-->
    </div>
    <!-- end custom-->
  </Container>
</template>
