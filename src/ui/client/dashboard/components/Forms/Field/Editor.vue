<script setup>
import {
  reactive,
  computed,
  defineEmits,
  onMounted,
  defineProps,
  onUnmounted,
  onBeforeMount,
} from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";
import Clipboard from "@components/Forms/Feature/Clipboard.vue";
import { useUUID } from "@utils/global.js";

import "@assets/script/editor/ace.js";
import "@assets/script/editor/theme-dracula.js";
import "@assets/script/editor/theme-dawn.js";

/**
 *  @name Forms/Field/Editor.vue
 *  @description This component is used to create a complete editor field  with error handling and label.
 *  We can also add popover to display more information.
 *  It is mainly use in forms.
 *  @example
 *  {
 *    id: "test-editor",
 *    value: "yes",
 *    name: "test-editor",
 *    disabled: false,
 *    required: true,
 *    pattern: "(test)",
 *    label: "Test editor",
 *    tabId: "1",
 *    columns: { pc: 12, tablet: 12, mobile: 12 },
 *  };
 *  @param {String} [id=uuidv4()] - Unique id
 *  @param {String} label - The label of the field. Can be a translation key or by default raw text.
 *  @param {String} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
 *  @param {String} value
 *  @param {Object} [attrs={}] - Additional attributes to add to the field
 *  @param {Array} [popovers=[]] - List of popovers to display more information
 *  @param {String} [inpType="editor"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
 *  @param {Object} [columns={"pc": "12", "tablet": "12", "mobile": "12"}] - Field has a grid system. This allow to get multiple field in the same row if needed.
 *  @param {String} [pattern=""]
 *  @param {Boolean} [disabled=false]
 *  @param {Boolean} [required=false]
 *  @param {Boolean} [isClipboard=true] - allow to copy the input value
 *  @param {Boolean} [hideLabel=false]
 *  @param {String} [containerClass=""]
 *  @param {String} [inpClass=""]
 *  @param {String} [headerClass=""]
 *  @param {String|Number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
 *  @param {String} [fieldSize="normal"] - Size between "normal" or "sm"
 *  @param {Boolean} [showErrMsg=false] - Show additionnal required or invalid error message at the bottom of the input. Disable by default because help popover, label and outline color are enough for the user.
 */
const props = defineProps({
  // id && value && method
  id: {
    type: String,
    required: false,
    default: "",
  },
  showErrMsg: {
    type: Boolean,
    required: false,
    default: false,
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
  attrs: {
    type: Object,
    required: false,
    default: {},
  },
  inpType: {
    type: String,
    required: false,
    default: "editor",
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
  pattern: {
    type: String,
    required: false,
    default: "",
  },
  isClipboard: {
    type: Boolean,
    required: false,
    default: true,
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
  fieldSize: {
    type: String,
    required: false,
    default: "normal",
  },
});

const editor = reactive({
  id: "",
  value: props.value,
  showInp: false,
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
    this.editor = ace.edit(editor.id);
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
          console.error(err);
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
          console.error(err);
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

/**
 *  @name removeErrCSS
 *  @description Remove useless CSS from the editor to avoid accessibility issues.
 *  @returns {Void}
 */
function removeErrCSS() {
  setTimeout(() => {
    try {
      const styleEditors = document.querySelectorAll(
        '[style*="font-optical-sizing"]'
      );

      styleEditors.forEach((editor) => {
        const dictStyle = JSON.parse(JSON.stringify(editor.style));
        // Loop and remove key if value is 'font-optical-sizing'
        for (const [key, value] of Object.entries(dictStyle)) {
          if (value === "font-optical-sizing") {
            delete dictStyle[key];
          }
        }
        editor.style = dictStyle;
      });
    } catch (e) {
      console.error(e);
    }
  }, 100);
}

/**
 *  @name setEditorAttrs
 *  @description Override editor attributes by adding or deleting some for better accessibility.
 *  @returns {Void}
 */
function setEditorAttrs() {
  // Add tabindex to editor
  try {
    const editorArea = document.querySelector("textarea.ace_text-input");
    // Set attributes
    editorArea.removeAttribute("wrap");
    editorArea.removeAttribute("autocorrect");

    editorArea.tabIndex = contentIndex;
    editorArea.setAttribute("id", `${editor.id}-editor`);
    editorArea.setAttribute("name", props.name);
    // Focus on editor
    editorArea.addEventListener("focus", (e) => {
      const editorRange = editorEl.editor.getSelectionRange();
      editorEl.editor.gotoLine(editorRange.start.row, editorRange.start.column);
    });
  } catch (e) {
    console.error(e);
  }
}

onBeforeMount(() => {
  editor.id = useUUID(props.id);
});

// Use ace editor
onMounted(() => {
  setTimeout(() => {
    // Default value
    editorEl = new Editor();
    editorEl.setValue(editor.value);
    editorEl.readOnlyBool(props.disabled);
    editorEl.editor.on("change", () => {
      editor.value = editorEl.getValue();
      // emit inp
      emits("inp", editor.value);
    });

    setEditorAttrs();
    removeErrCSS();
  }, 10);
});

onUnmounted(() => {
  try {
    editorEl.destroy();
  } catch (err) {}
});
</script>

<template>
  <Container
    :containerClass="`${props.containerClass} input-container`"
    :columns="props.columns"
  >
    <Header
      :popovers="props.popovers"
      :required="props.required"
      :name="props.name"
      :label="props.label"
      :id="`${editor.id}-editor`"
      :hideLabel="props.hideLabel"
      :headerClass="props.headerClass"
      :fieldSize="props.fieldSize"
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
        v-bind="props.attrs"
        :class="[
          'input-editor',
          props.disabled ? 'disabled' : 'enabled',
          props.inpClass,
        ]"
        :aria-description="$t('inp_editor_desc')"
        :id="editor.id"
      ></div>
      <Clipboard
        :isClipboard="props.isClipboard"
        :clipboardClass="'editor-clip'"
        :copyClass="'editor-clip'"
        :valueToCopy="editor.value"
      />
    </div>
    <ErrorField
      v-if="props.showErrMsg"
      :errorClass="'editor'"
      :isValid="editor.isValid"
      :isValue="!!editor.value"
    />
  </Container>
</template>
