<script setup>
import { defineProps, onBeforeMount, reactive } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { useClipboard } from "@vueuse/core";
import { useUUID } from "@utils/global.js";

/**
  @name Forms/Feature/Clipboard.vue
  @description This component can be add to some fields to allow to copy the value of the field.
  Additionnal clipboardClass and copyClass can be added to fit the parent container.
  @example
  {
    id: 'test-input',
    isClipboard: true,
    valueToCopy: 'yes',
    clipboadClass: 'mx-2',
    copyClass: 'mt-2',
  }
  @param {id} [id=uuidv4()] - Unique id
  @param {isClipboard} [isClipboard=false] - Display a clipboard button to copy a value
  @param {valueToCopy} [valueToCopy=""] - The value to copy
  @param {clipboadClass} [clipboadClass=""] - Additional class for the clipboard container. Useful to fit the component in a specific container.
  @param {copyClass} [copyClass=""] - The class of the copy message. Useful to fit the component in a specific container.
*/

const { text, copy, copied, isSupported } = useClipboard({ legacy: true });

const props = defineProps({
  id: {
    type: String,
    required: false,
    default: "",
  },
  isClipboard: {
    type: Boolean,
    required: false,
    default: false,
  },
  valueToCopy: {
    type: [String, Number],
    required: false,
    default: "",
  },
  clipboardClass: {
    type: String,
    required: false,
    default: "",
  },
  copyClass: {
    type: String,
    required: false,
    default: "",
  },
});

const clip = reactive({
  id: "",
});

onBeforeMount(() => {
  clip.id = useUUID(props.id);
});
</script>

<template>
  <div
    v-if="props.isClipboard"
    :class="['input-clipboard-container', props.clipboardClass]"
  >
    <button
      type="button"
      :class="['input-clipboard-button', copied ? 'copied' : 'not-copied']"
      :tabindex="contentIndex"
      @click.prevent="copy(`${valueToCopy}`)"
      :aria-labelledby="`${clip.id}-clipboard-text`"
    >
      <span :id="`${clip.id}-clipboard-text`" class="sr-only">
        {{ $t("inp_input_clipboard_desc") }}
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
      <div
        v-if="copied"
        role="alert"
        :class="['input-clipboard-copy', props.copyClass]"
      >
        {{ $t("inp_input_clipboard_copied") }}
      </div>
    </button>
  </div>
</template>
