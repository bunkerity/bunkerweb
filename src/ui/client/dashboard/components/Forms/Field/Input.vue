<script setup>
import {
  reactive,
  ref,
  defineEmits,
  onMounted,
  onBeforeMount,
  defineProps,
} from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";
import Clipboard from "@components/Forms/Feature/Clipboard.vue";
import { useUUID } from "@utils/global.js";

/**
 *  @name Forms/Field/Input.vue
 *  @description This component is used to create a complete input field input with error handling and label.
 *  We can add a clipboard button to copy the input value.
 *  We can also add a password button to show the password.
 *  We can also add popover to display more information.
 *  It is mainly use in forms.
 *  @example
 *  {
 *    id: 'test-input',
 *    value: 'yes',
 *    type: "text",
 *    name: 'test-input',
 *    disabled: false,
 *    required: true,
 *    label: 'Test input',
 *    pattern : "(test)",
 *    inpType: "input",
 *    popovers : [
 *      {
 *        text: "This is a popover text",
 *        iconName: "info",
 *      },
 *    ],
 *  }
 *  @param {string} [id=uuidv4()] - Unique id
 *  @param {string} [type="text"] - text, email, password, number, tel, url
 *  @param {string} label - The label of the field. Can be a translation key or by default raw text.
 *  @param {string} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
 *  @param {string} value
 *  @param {object} [attrs={}] - Additional attributes to add to the field
 *  @param {array} [popovers] - List of popovers to display more information
 *  @param {string} [inpType="input"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
 *  @param {object} [columns={"pc": "12", "tablet": "12", "mobile": "12"}] - Field has a grid system. This allow to get multiple field in the same row if needed.
 *  @param {boolean} [disabled=false]
 *  @param {boolean} [required=false]
 *  @param {string} [placeholder=""]
 *  @param {string} [pattern="(?.*)"]
 *  @param {boolean} [isClipboard=true] - allow to copy the input value
 *  @param {boolean} [readonly=false] - allow to read only the input value
 *  @param {boolean} [hideLabel=false]
 *  @param {string} [containerClass=""]
 *  @param {string} [inpClass=""]
 *  @param {string} [headerClass=""]
 *  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
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
  name: {
    type: String,
    required: true,
  },
  type: {
    type: String,
    required: false,
    default: "text",
  },
  attrs: {
    type: Object,
    required: false,
    default: {},
  },
  inpType: {
    type: String,
    required: false,
    default: "input",
  },
  required: {
    type: Boolean,
    required: false,
    default: false,
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
  value: {
    type: String,
    required: true,
  },
  placeholder: {
    type: String,
    required: false,
    default: "",
  },
  pattern: {
    type: String,
    required: false,
    default: "(?s).*",
  },
  isClipboard: {
    type: Boolean,
    required: false,
    default: true,
  },
  readonly: {
    type: Boolean,
    required: false,
    default: false,
  },
  label: {
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

const inputEl = ref(null);

const inp = reactive({
  id: "",
  value: props.value,
  showInp: false,
  isValid: true,
});

const emits = defineEmits(["inp"]);

onBeforeMount(() => {
  inp.id = useUUID(props.id);
});

onMounted(() => {
  inp.isValid = inputEl.value.checkValidity();

  // Clipboard not allowed on http
  if (!window.location.href.startsWith("https://")) return;
});
</script>

<template>
  <Container
    :containerClass="`${props.containerClass}`"
    :columns="props.columns"
  >
    <Header
      :popovers="props.popovers"
      :required="props.required"
      :name="props.name"
      :label="props.label"
      :id="inp.id"
      :hideLabel="props.hideLabel"
      :headerClass="props.headerClass"
    />

    <div class="input-regular-container">
      <input
        v-bind="props.attrs"
        :tabindex="props.tabId"
        ref="inputEl"
        v-model="inp.value"
        @input="
          () => {
            inp.isValid = inputEl.checkValidity();
            $emit('inp', inp.value);
          }
        "
        :id="inp.id"
        :class="[
          'input-regular',
          inp.isValid ? 'valid' : 'invalid',
          props.inpClass,
        ]"
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
        :pattern="props.pattern || '(?s).*'"
        :name="props.name"
        :value="inp.value"
        :type="
          props.type === 'password'
            ? inp.showInp
              ? 'text'
              : 'password'
            : props.type
        "
      />
      <Clipboard
        :isClipboard="props.isClipboard"
        :valueToCopy="inp.value"
        :clipboardClass="
          props.type === 'password' ? 'pw-input-clip' : 'no-pw-input-clip'
        "
        :copyClass="'input-clip'"
      />

      <div v-if="props.type === 'password'" class="input-pw-container">
        <button
          :tabindex="contentIndex"
          :aria-controls="inp.id"
          @click.prevent="inp.showInp = inp.showInp ? false : true"
          :class="[props.disabled ? 'disabled' : 'enabled']"
          class="input-pw-button"
          :aria-labelledby="`${inp.id}-password-text`"
        >
          <span :id="`${inp.id}-password-text`" class="sr-only">{{
            $t("inp_input_password_desc")
          }}</span>
          <svg
            role="img"
            aria-hidden="true"
            v-if="!inp.showInp"
            class="input-pw-svg"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 576 512"
          >
            <path
              d="M288 32c-80.8 0-145.5 36.8-192.6 80.6C48.6 156 17.3 208 2.5 243.7c-3.3 7.9-3.3 16.7 0 24.6C17.3 304 48.6 356 95.4 399.4C142.5 443.2 207.2 480 288 480s145.5-36.8 192.6-80.6c46.8-43.5 78.1-95.4 93-131.1c3.3-7.9 3.3-16.7 0-24.6c-14.9-35.7-46.2-87.7-93-131.1C433.5 68.8 368.8 32 288 32zM432 256c0 79.5-64.5 144-144 144s-144-64.5-144-144s64.5-144 144-144s144 64.5 144 144zM288 192c0 35.3-28.7 64-64 64c-11.5 0-22.3-3-31.6-8.4c-.2 2.8-.4 5.5-.4 8.4c0 53 43 96 96 96s96-43 96-96s-43-96-96-96c-2.8 0-5.6 .1-8.4 .4c5.3 9.3 8.4 20.1 8.4 31.6z"
            />
          </svg>
          <svg
            role="img"
            aria-hidden="true"
            v-if="inp.showInp"
            class="input-pw-svg scale-110"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 640 512"
          >
            <path
              d="M38.8 5.1C28.4-3.1 13.3-1.2 5.1 9.2S-1.2 34.7 9.2 42.9l592 464c10.4 8.2 25.5 6.3 33.7-4.1s6.3-25.5-4.1-33.7L525.6 386.7c39.6-40.6 66.4-86.1 79.9-118.4c3.3-7.9 3.3-16.7 0-24.6c-14.9-35.7-46.2-87.7-93-131.1C465.5 68.8 400.8 32 320 32c-68.2 0-125 26.3-169.3 60.8L38.8 5.1zM223.1 149.5C248.6 126.2 282.7 112 320 112c79.5 0 144 64.5 144 144c0 24.9-6.3 48.3-17.4 68.7L408 294.5c5.2-11.8 8-24.8 8-38.5c0-53-43-96-96-96c-2.8 0-5.6 .1-8.4 .4c5.3 9.3 8.4 20.1 8.4 31.6c0 10.2-2.4 19.8-6.6 28.3l-90.3-70.8zm223.1 298L373 389.9c-16.4 6.5-34.3 10.1-53 10.1c-79.5 0-144-64.5-144-144c0-6.9 .5-13.6 1.4-20.2L83.1 161.5C60.3 191.2 44 220.8 34.5 243.7c-3.3 7.9-3.3 16.7 0 24.6c14.9 35.7 46.2 87.7 93 131.1C174.5 443.2 239.2 480 320 480c47.8 0 89.9-12.9 126.2-32.5z"
            />
          </svg>
        </button>
      </div>
      <ErrorField
        :errorClass="'input'"
        :isValid="inp.isValid"
        :isValue="!!inp.value"
      />
    </div>
  </Container>
</template>
