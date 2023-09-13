<script setup>
import {
  computed,
  defineProps,
  defineEmits,
  reactive,
  onMounted,
  onUnmounted,
  onUpdated,
} from "vue";
import ModalBase from "@components/Modal/Base.vue";
import ButtonBase from "@components/Button/Base.vue";
import AlertBase from "@components/Alert/Base.vue";
import "@assets/script/editor/ace.js";
import "@assets/script/editor/theme-dracula.js";
import "@assets/script/editor/theme-dawn.js";

// Open after a file manager item (folder / file) action is clicked
// With the current folder / file data
// Update name or content file if wanted
const props = defineProps({
  // File or folder
  type: {
    type: String,
    required: true,
  },
  // view || edit || download || delete
  action: {
    type: String,
    required: true,
  },
  // Current item path
  path: {
    type: String,
    required: true,
  },
  // File value is shown with an editor
  value: {
    type: String,
    required: true,
  },
});

// Filter data from path
const oldName = computed(() => {
  return props.path.split("/")[props.path.split("/").length - 1];
});

const prefix = computed(() => {
  const arr = props.path.split("/");
  arr.pop();
  return `${arr.join("/")}/`;
});

const inp = reactive({
  name: "",
});

// Ace editor vanilla logic
class FileEditor {
  constructor() {
    this.editor = ace.edit("editor");
    this.darkMode = document.querySelector("[data-dark-toggle]");
    this.initEditor();
    this.listenDarkToggle();
  }

  initEditor() {
    //editor options
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
}

let editor = null;

// Use ace editor
onMounted(() => {
  try {
    editor = new FileEditor();
    console.log(editor);
  } catch (err) {}
});

onUpdated(() => {
  try {
    editor = new FileEditor();
  } catch (err) {}
});

onUnmounted(() => {
  try {
    editor.destroy();
  } catch (err) {}
});

const alert = reactive({
  isOpen: false,
  message: "",
  type: "",
});

function showAlert(type, message) {
  alert.message = message;
  alert.type = type;
  alert.isOpen = true;
}

const emits = defineEmits(["createFile", "close"]);
</script>
<template>
  <ModalBase :title="`${props.action} file`">
    <div class="w-full">
      <div class="modal-path">
        <p class="modal-path-text">
          {{ prefix }}
        </p>
        <input
          @input="inp.name = $event.target.value"
          type="text"
          name="name"
          id="name"
          :value="inp.name || oldName"
          class="modal-input"
          :placeholder="'filename'"
          :disabled="props.action === 'view'"
          required
        />
        <p class="ml-1 modal-path-text">.conf</p>
      </div>

      <!-- editor-->
      <div id="editor" class="modal-editor">
        {{ props.value }}
      </div>
      <!-- editor-->
      <AlertBase
        :message="alert.message"
        :type="alert.type"
        v-if="alert.isOpen"
        @close="alert.isOpen = false"
      />
      <div class="mt-2 w-full justify-end flex">
        <ButtonBase size="lg" @click="$emit('close')" class="btn-close text-xs">
          Close
        </ButtonBase>
        <ButtonBase
          @click="
            () => {
              if (!inp.name)
                return showAlert(
                  'error',
                  `Filename missing to create element.`
                );

              if (!editor.getValue()) {
                inp.name = inp.name;
                return showAlert('error', 'Missing content to create file.');
              }

              $emit('createFile', {
                action: props.action,
                path: props.path,
                name: inp.name,
                data: editor.getValue(),
              });
            }
          "
          size="lg"
          v-if="props.action !== 'view'"
          :class="[
            props.action === 'edit' ? 'btn-edit' : '',
            props.action === 'download' ? 'btn-download' : '',
            props.action === 'delete' ? 'btn-delete' : '',
            props.action === 'create' ? 'btn-valid' : '',
          ]"
          class="text-xs ml-2"
        >
          {{ props.action }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
