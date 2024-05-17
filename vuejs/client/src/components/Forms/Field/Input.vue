<script setup>
import { reactive, ref, defineEmits, onMounted, defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";


/* 
  This input component is used to create a complete input (label, validator message).
  It is mainly use for input setting form.  

  PROPS ARGUMENTS
  *
  *
  id: string,
  columns : <object|boolean>,
  name: string,
  type: string<"text"|"email"|"password"|"number"|"tel"|"url">,
  disabled: boolean,
  value: string,
  placeholder: string,
  pattern: string,
  clipboard: boolean,
  readonly: boolean,
  label: string,
  name: string,
  version: string,
  hideLabel: boolean,
  required: boolean,
  containerClass: string,
  headerClass: string,
  inpClass: string,
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
    columns : {
      type : [Object, Boolean],
      required: false,
      default : false
    },
    name: {
        type: String,
        required: true,
    },
    type: {
        type: String,
        required: true,
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
    },
    readonly: {
        type: Boolean,
        required: false,
    },
    label: {
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
    containerClass : {
      type: String,
      required: false
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
        required: true,
    },

});


const inputEl = ref(null);

const inp = reactive({
  value: props.value,
  showInp: false,
  isClipAllow: false,
  isValid: false,
});

const emits = defineEmits(["inp"]);

function copyClipboard() {
  if (!inp.clipboard || !inp.isClipAllow) return;

  navigator.permissions.query({ name: "clipboard-write" }).then((result) => {
    if (result.state === "granted" || result.state === "prompt") {
      /* write to the clipboard now */

      inputEl.select();
      inputEl.setSelectionRange(0, 99999); // For mobile devices

      // Copy the text inside the text field
      return navigator.clipboard.writeText(inputEl.value);
    }
  });
}

onMounted(() => {
  inp.isValid = inputEl.value.checkValidity();
  // Clipboard not allowed on http
  if (!window.location.href.startsWith("https://")) return;

  // Check clipboard permission
  navigator.permissions.query({ name: "clipboard-write" }).then((result) => {
    if (result.state === "granted" || result.state === "prompt") {
      inp.isClipAllow = true;
      return;
    }
  });
});
</script>

<template>
  <Container :containerClass="`w-full m-1 p-1 ${props.containerClass}`" :columns="props.columns">
  <Header :required="props.required" :name="props.name" :label="props.label" :hideLabel="props.hideLabel" :headerClass="props.headerClass" />

  <div class="relative flex flex-col items-start">
    <input
      :tabindex="props.tabId || contentIndex"
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
      :placeholder="props.placeholder || ''"
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
      v-if="props.clipboard && inp.isClipAllow"
      :class="[props.type === 'password' ? 'pw-input' : 'no-pw-input']"
      class="input-clipboard-container"
    >
      <button
        :tabindex="contentIndex"
        @click="copyClipboard()"
        :class="[props.disabled ? 'disabled' : 'enabled']"
        class="input-clipboard-button"
        :aria-describedby="`${props.id}-clipboard-text`"
      >
        <span :id="`${props.id}-clipboard-text`" class="sr-only"
          >{{ $t("inp_input_clipboard_desc") }}
        </span>
        <svg
          role="img"
          aria-hidden="true"
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
            d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184"
          />
        </svg>
      </button>
    </div>
    <div v-if="props.type === 'password'" class="input-pw-container">
      <button
        :tabindex="contentIndex"
        :aria-description="$t('inp_input_password_desc')"
        :aria-controls="props.id"
        @click="inp.showInp = inp.showInp ? false : true"
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
    <p
      :aria-hidden="inp.isValid ? 'true' : 'false'"
      role="alert"
      :class="[inp.isValid ? 'hidden' : '']"
      class="input-error-msg"
    >
      {{
        inp.isValid
          ? $t("inp_input_valid")
          : !inp.value
            ? $t("inp_input_error_required")
            : $t("inp_input_error_format")
      }}
    </p>
  </div>
  </Container>
</template>