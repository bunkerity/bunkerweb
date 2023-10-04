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
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";

const feedbackStore = useFeedbackStore();

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

const emits = defineEmits(["close", "updateFile"]);

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

  setValue(content) {
    return this.editor.setValue(content, 1);
  }
}

let editor = null;

// Use ace editor
onMounted(() => {
  try {
    editor = new FileEditor();
    editor.setValue(props.value);
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

const updateConf = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

function createFile() {
  // Case no name
  if (!inp.name) return showAlert("error", `Filename missing to create conf`);

  // Case no content
  if (!editor.getValue()) {
    inp.name = inp.name;
    return showAlert("error", "Missing content to create conf");
  }
  // Format data
  const splitPath = props.path.replace("root/", "").trim().split("/");
  !splitPath[splitPath.length - 1] ? splitPath.pop() : false;
  const type = splitPath[0].replaceAll("-", "_");
  const serviceID = splitPath[1] ? splitPath[1] : "";

  const conf = [
    {
      service_id: serviceID,
      type: type,
      name: inp.name || oldName,
      data: editor.getValue(),
    },
  ];

  updateConfig(conf);
  if (props.action === "delete") deleteConfig(conf);
}

async function updateConfig(conf) {
  showAlert("info", `Try to ${props.action} conf.`);
  // We want to close modal only if communication with API worked
  // To avoid input removing on close
  const api =
    props.action === `delete`
      ? `/api/custom_configs/${conf.name}?method=ui`
      : `/api/custom_configs?method=ui`;
  const method = props.action === `delete` ? `DELETE` : `PUT`;

  await fetchAPI(api, method, conf, updateConf, feedbackStore.addFeedback)
    .then((res) => {
      if (res.type === "error")
        return showAlert("error", "Failed to save conf");
      alert.isOpen = false;
      emits("close");
      emits("updateFile");
    })
    .catch((err) => {
      showAlert("error", "Failed to save conf");
    });
}

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
          @click="createFile()"
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
