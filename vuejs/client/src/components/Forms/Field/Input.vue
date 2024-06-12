<script setup>
import { reactive, ref, defineEmits, onMounted, defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";
import { v4 as uuidv4 } from "uuid";
import { useClipboard } from "@vueuse/core";

/**
  @name Forms/Field/Input.vue
  @description This component is used to create a complete input field input with error handling and label.
  We can add a clipboard button to copy the input value.
  We can also add a password button to show the password.
  We can also add popover to display more information.
  It is mainly use in forms.
  @example
  {
    id: 'test-input',
    value: 'yes',
    type: "text",
    name: 'test-input',
    disabled: false,
    required: true,
    label: 'Test input',
    pattern : "(test)",
    inpType: "input",
    popovers : [
      {
        text: "This is a popover text",
        iconName: "info",
        iconColor: "info",
      },
    ],
  }
  @param {string} [id=uuidv4()] - Unique id 
  @param {string} type - text, email, password, number, tel, url
  @param {string} label - The label of the field. Can be a translation key or by default raw text.
  @param {string} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.  @param {string} label
  @param {string} value
  @param {array} [popovers] - List of popovers to display more information
  @param {string} [inpType="input"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
  @param {object} [columns={"pc": "12", "tablet": "12", "mobile": "12}] - Field has a grid system. This allow to get multiple field in the same row if needed.
  @param {boolean} [disabled=false]
  @param {boolean} [required=false]
  @param {string} [placeholder=""]
  @param {string} [pattern="(?.*)"]
  @param {boolean} [clipboard=false] - allow to copy the input value
  @param {boolean} [readonly=false] - allow to read only the input value
  @param {boolean} [hideLabel=false]
  @param {string} [containerClass=""]
  @param {string} [inpClass=""]
  @param {string} [headerClass=""]
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const { text, copy, copied, isSupported } = useClipboard({ legacy: true });

const props = defineProps({
  // id && value && method
  id: {
    type: String,
    required: false,
    default: uuidv4(),
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
    required: true,
  },
  inpType: {
    type: String,
    required: false,
    default: "input",
  },
  required: {
    type: Boolean,
    required: false,
  },
  disabled: {
    type: Boolean,
    required: false,
  },
  value: {
    type: String,
    required: true,
  },
  placeholder: {
    type: String,
    required: false,
  },
  pattern: {
    type: String,
    required: false,
  },
  clipboard: {
    type: Boolean,
    required: false,
    default: true,
  },
  readonly: {
    type: Boolean,
    required: false,
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
  value: props.value,
  showInp: false,
  isClipAllow: false,
  isValid: true,
});

const emits = defineEmits(["inp"]);

onMounted(() => {
  inp.isValid = inputEl.value.checkValidity();

  // Clipboard not allowed on http
  if (!window.location.href.startsWith("https://")) return;
});
</script>

<template>
  <Container
    :containerClass="`field-container ${props.containerClass}`"
    :columns="props.columns"
  >
    <Header
      :popovers="props.popovers"
      :required="props.required"
      :name="props.name"
      :label="props.label"
      :hideLabel="props.hideLabel"
      :headerClass="props.headerClass"
    />

    <div class="input-regular-container">
      <input
        :tabindex="props.tabId"
        ref="inputEl"
        v-model="inp.value"
        @input="
          () => {
            inp.isValid = inputEl.checkValidity();
            $emit('inp', inp.value);
          }
        "
        :id="props.id"
        :class="[
          'input-regular',
          inp.isValid ? 'valid' : 'invalid',
          props.inpClass,
        ]"
        :required="props.required || false"
        :readonly="props.readonly || false"
        :disabled="props.disabled || false"
        :placeholder="
          props.placeholder ? $t(props.placeholder, props.placeholder) : ''
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
      <div
        v-if="props.clipboard"
        :class="[props.type === 'password' ? 'pw-input' : 'no-pw-input']"
        class="input-clipboard-container"
      >
        <button
          type="button"
          :class="['input-clipboard-button', copied ? 'copied' : 'not-copied']"
          :tabindex="contentIndex"
          @click.prevent="copy(inp.value)"
          :aria-describedby="`${props.id}-clipboard-text`"
        >
          <span :id="`${props.id}-clipboard-text`" class="sr-only"
            >{{ $t("inp_input_clipboard_desc") }}
          </span>
          <svg
            aria-hidden="true"
            role="img"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
            class="input-clipboard-svg"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M8.25 7.5V6.108c0-1.135.845-2.098 1.976-2.192.373-.03.748-.057 1.123-.08M15.75 18H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08M15.75 18.75v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5A3.375 3.375 0 0 0 6.375 7.5H5.25m11.9-3.664A2.251 2.251 0 0 0 15 2.25h-1.5a2.251 2.251 0 0 0-2.15 1.586m5.8 0c.065.21.1.433.1.664v.75h-6V4.5c0-.231.035-.454.1-.664M6.75 7.5H4.875c-.621 0-1.125.504-1.125 1.125v12c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V16.5a9 9 0 0 0-9-9Z"
            ></path>
          </svg>
          <div v-if="copied" role="alert" class="input input-clipboard-copy">
            {{ $t("inp_input_clipboard_copied") }}
          </div>
        </button>
      </div>

      <div v-if="props.type === 'password'" class="input-pw-container">
        <button
          :tabindex="contentIndex"
          :aria-description="$t('inp_input_password_desc')"
          :aria-controls="props.id"
          @click.prevent="inp.showInp = inp.showInp ? false : true"
          :class="[props.disabled ? 'disabled' : 'enabled']"
          class="input-pw-button"
        >
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
      <ErrorField :isValid="inp.isValid" :isValue="!!inp.value" />
    </div>
  </Container>
</template>
