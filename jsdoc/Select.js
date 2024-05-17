import { ref, reactive, watch, onMounted, defineEmits, defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";


/** 
  @name Select.vue
  @description This component is used to create a complete select field input with error handling and label.
  We can be more precise by adding values that need to be selected to be valid.
  We can also add popover to display more information.
  It is mainly use in forms.
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
  }
  @param {string} id
  @param {string} text - content of the button
  @param {string} [type="button"] - button || submit
  @param {boolean} [disabled=false]
  @param {boolean} [hideText=false] - hide text to only display icon
  @param {string} [color="primary"] 
  @param {string} [size="normal"] - sm || normal || lg || xl
  @param {string} [iconName=""] - store on components/Icons/Button
  @param {string} [iconColor=""]
  @param {object} [eventAttr={}] - {"store" : <store_name>, "default" : <default_value>,  "value" : <value_stored_on_click>, "target"<optional> : <target_id_element>, "valueExpanded" : "expanded_value"}
  @param {string|number} [tabId=""]
*/

const props = defineProps({
  // id && value && method
    id: {
        type: String,
        required: true,
    },
    columns: {
      type: [Object, Boolean],
      required: false,
      default: false
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
    requiredValues : {
      type: Array,
      required: false,
      default : []
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
        default : ""
    },
    hideLabel: {
        type: Boolean,
        required: false,
    },
    containerClass : {
      type: String,
      required: false,
      default : ""
    },
    headerClass: {
        type: String,
        required: false,
        default : ""
    },
    inpClass: {
        type: String,
        required: false,
        default : ""
    },
    tabId: {
        type: [String, Number],
        required: false,
        default: ""
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
  isValid: !props.required ? true : props.requiredValues.length <= 0 ? true : props.requiredValues.includes(props.value) ? true : false,
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
  // Check if value is required and if it is in requiredValues
  select.isValid = !props.required ? true : props.requiredValues.length <= 0 ? true : props.requiredValues.includes(newValue) ? true : false;
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