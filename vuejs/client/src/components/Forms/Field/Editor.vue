<script setup>
import {
  reactive,
  ref,
  computed,
  defineEmits,
  onMounted,
  defineProps,
  onUnmounted,
} from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";
import { v4 as uuidv4 } from "uuid";
import "@assets/script/editor/ace.js";
import "@assets/script/editor/theme-dracula.js";
import "@assets/script/editor/theme-dawn.js";
/**
  @name Forms/Field/Editor.vue
  @description This component is used to create a complete editor field input with error handling and label.
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
  @param {string} label - The label of the field. Can be a translation key or by default raw text.
  @param {string} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.  @param {string} label
  @param {string} value
  @param {array} [popovers] - List of popovers to display more information
  @param {string} [inpType="editor"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
  @param {object} [columns={"pc": "12", "tablet": "12", "mobile": "12}] - Field has a grid system. This allow to get multiple field in the same row if needed.
  @param {string} [pattern=""]
  @param {boolean} [disabled=false]
  @param {boolean} [required=false]
  @param {boolean} [clipboard=false] - allow to copy the input value
  @param {boolean} [hideLabel=false]
  @param {string} [containerClass=""]
  @param {string} [editorClass=""]
  @param {string} [headerClass=""]
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

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
  inpType: {
    type: String,
    required: false,
    default: "editor",
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
  pattern: {
    type: String,
    required: false,
    defaut: "",
  },
  clipboard: {
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
  editorClass: {
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

const editor = reactive({
  value: props.value,
  showInp: false,
  isClipAllow: false,
  isValid: computed(() => {
    if (props.required && !editor.value) return false;
    if (props.pattern) {
      const regex = new RegExp(props.pattern);
      return regex.test(editor.value);
    }
    return true;
  }),
});

const emits = defineEmits(["inp"]);

let editorEl = null;

// Ace editor vanilla logic
class Editor {
  constructor() {
    this.editor = ace.edit(props.id);
    this.darkMode = document.querySelector("[data-dark-toggle]");
    this.initEditor();
    this.listenDarkToggle();
  }

  initEditor() {
    // handle tabindex
    this.editor.commands.addCommand({
      name: "prevTabIndex",
      bindKey: { win: "Shift-Tab", mac: "Shift-Tab" },
      exec: function (editor) {
        try {
          // Get all elements with the same tabindex
          const elements = document.querySelectorAll(
            `[tabindex="${contentIndex}"]`
          );
          // Get index of the current element
          const index = Array.from(elements).indexOf(document.activeElement);
          // Focus on the next element if exists
          if (elements[index - 1]) return elements[index - 1].focus();
          // Else try to find tabIndex + 1 element
          const prevElements = document.querySelectorAll(
            `[tabindex="${+contentIndex - 1}"]`
          );
          // Else find the highest tabindex element in a limit of +20
          let maxTabIndex = -10;
          let currTabIndex = +contentIndex - 1;
          while (currTabIndex > maxTabIndex) {
            const minElements = document.querySelectorAll(
              `[tabindex="${currTabIndex}"]`
            );
            if (minElements[0]) return minElements[0].focus();
            currTabIndex++;
          }
        } catch (err) {
          console.log(err);
        }
      },
      readOnly: true,
    });

    this.editor.commands.addCommand({
      name: "NextTabIndex",
      bindKey: { win: "Tab", mac: "Tab" },
      exec: function (editor) {
        try {
          // Get all elements with the same tabindex
          const elements = document.querySelectorAll(
            `[tabindex="${contentIndex}"]`
          );
          // Get index of the current element
          const index = Array.from(elements).indexOf(document.activeElement);
          // Focus on the next element if exists
          if (elements[index + 1]) return elements[index + 1].focus();
          // Else find the highest tabindex element in a limit of +20
          let maxTabIndex = +contentIndex + 20;
          let currTabIndex = +contentIndex + 1;
          while (currTabIndex < maxTabIndex) {
            const maxElements = document.querySelectorAll(
              `[tabindex="${currTabIndex}"]`
            );
            if (maxElements[0]) return maxElements[0].focus();
            currTabIndex++;
          }
        } catch (err) {
          console.log(err);
        }
      },
      readOnly: true,
    });

    this.editor.setShowPrintMargin(false);
    this.setDarkMode();
  }

  //listen to dark toggle button to change theme
  listenDarkToggle() {
    this.darkMode.addEventListener("click", (e) => {
      this.darkMode.checked
        ? this.changeDarkMode(true)
        : this.changeDarkMode(false);
    });
  }

  setDarkMode() {
    document.querySelector("html").className.includes("dark")
      ? this.editor.setTheme("ace/theme/dracula")
      : this.editor.setTheme("ace/theme/dawn");
  }

  //change theme according to mode
  changeDarkMode(bool) {
    bool
      ? this.editor.setTheme("ace/theme/dracula")
      : this.editor.setTheme("ace/theme/dawn");
  }

  readOnlyBool(bool) {
    this.editor.setReadOnly(bool);
  }

  destroy() {
    this.editor.destroy();
  }

  getValue() {
    return this.editor.getValue();
  }

  setValue(content) {
    return this.editor.setValue(content, 1);
  }
}

// Use ace editor
onMounted(() => {
  // Default value
  editorEl = new Editor();
  editorEl.setValue(editor.value);
  editorEl.readOnlyBool(props.disabled);
  editorEl.editor.on("change", () => {
    editor.value = editorEl.getValue();
  });
  // Add tabindex to editor
  try {
    const editorArea = document.querySelector("textarea.ace_text-input");
    editorArea.tabIndex = contentIndex;
    editorArea.setAttribute("name", props.name);
  } catch (e) {}
});

onUnmounted(() => {
  try {
    editorEl.destroy();
  } catch (err) {}
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

    <div
      :class="[
        'input-editor-container',
        props.disabled ? 'disabled' : 'enabled',
      ]"
    >
      <div
        v-if="(!editor.value && props.required) || !editor.isValid"
        class="input-editor-error"
      ></div>
      <div
        :class="['input-editor', props.disabled ? 'disabled' : 'enabled']"
        :aria-description="$t('inp_editor_desc')"
        :id="props.id"
      ></div>
      <div
        v-if="props.clipboard && inp.isClipAllow"
        :class="[props.type === 'password' ? 'pw-input' : 'no-pw-input']"
        class="input-clipboard-container"
      >
        <button
          :tabindex="contentIndex"
          @click.prevent="copyClipboard()"
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
    </div>
    <ErrorField :isValid="editor.isValid" :isValue="!!editor.value" />
  </Container>
</template>
