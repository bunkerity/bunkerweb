<script setup>
import {
  computed,
  defineProps,
  defineEmits,
  reactive,
  onMounted,
  onUnmounted,
  onBeforeUpdate,
  onUpdated,
} from "vue";
import ModalBase from "@components/Modal/Base.vue";
import ButtonBase from "@components/Button/Base.vue";
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
  isOpen: {
    type: Boolean,
    required: true,
  },
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
    default: "",
  },
  // Method to avoid override static ones
  method: {
    type: String,
    required: true,
    default: "",
  },
});

const emits = defineEmits(["close", "updateFile"]);

// Filter data from path

const data = reactive({
  name: "",
  oldName: props.path.split("/")[props.path.split("/").length - 1],
  value: props.value,
  method: props.method,
  prefix: computed(() => {
    const arr = props.path.split("/");
    arr.pop();
    return `${arr.join("/")}/`;
  }),
  isReadOnly: computed(() => {
    if (props.type !== "file") return true;
    if (
      props.action.toLowerCase() === "view" ||
      props.action.toLowerCase() === "delete"
    )
      return true;
    return false;
  }),
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
  // default value
  data.name = data.oldName;
  if (props.type !== "file") return;
  editor = new FileEditor();
  editor.setValue(props.value);
  editor.readOnlyBool(data.isReadOnly);
  editor.editor.on("change", () => {
    data.value = editor.getValue();
  });
});

onBeforeUpdate(() => {
  data.oldName = props.path.split("/")[props.path.split("/").length - 1];
  data.name = data.oldName;
  data.value = props.value;
  data.method = props.method;
  try {
    editor.destroy();
  } catch (err) {}
});

onUpdated(() => {
  if (props.type === "file") {
    // default value
    data.name = data.oldName;
    if (props.type !== "file") return;
    editor = new FileEditor();
    editor.setValue(props.value);
    editor.readOnlyBool(data.isReadOnly);
    editor.editor.on("change", () => {
      data.value = editor.getValue();
    });
  }
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

function formatData() {
  // Format data, we need to remove root that is only functional
  // And the current file name to keep only type/service?
  const splitPath = props.path
    .replaceAll("-", "_")
    .replace("root/", "")
    .replace(`${data.oldName}`, "")
    .trim()
    .split("/")
    .filter((item) => item !== "");

  const conf = {
    service_id: splitPath[1] ? splitPath[1] : "",
    type: splitPath[0],
    name: data.name,
    old_name: data.oldName,
    data: data.value,
    method: data.method,
  };

  return conf;
}

async function sendData() {
  // Send only if filename and content
  if (!data.name && !data.value) return;

  // Case all needed data
  const conf = formatData();
  const method = props.action.toLowerCase() === "delete" ? "DELETE" : "PUT";
  const baseURL = `/api/custom_configs${
    method === "DELETE" ? `/${conf.old_name}` : ``
  }`;
  const queries =
    props.action.toLowerCase() === "delete"
      ? `?method=ui&custom_config_name=${conf.old_name}&config_type=${conf.type}&service_id=${conf.service_id}`
      : `?method=ui`;
  const api = `${baseURL}${queries}`;
  // Fetch
  await fetchAPI(
    api,
    method,
    props.action.toLowerCase() === "delete" ? null : conf,
    updateConf,
    feedbackStore.addFeedback,
  )
    .then((res) => {
      // Case not save
      if (res.type === "success") {
        // Case saved
        emits("close");
        emits("updateFile");
        return;
      }
    })
    .catch((err) => {});
}
</script>
<template>
  <ModalBase
    v-show="props.isOpen"
    :aria-hidden="props.isOpen ? 'false' : 'true'"
    id="file-manager-modal"
    @backdrop="$emit('close')"
    :title="
      $t('custom_conf_modal_title', { action: $t(`action_${props.action}`) })
    "
  >
    <div class="w-full">
      <div
        role="group"
        :aria-description="$t('custom_conf_modal_path_desc')"
        class="modal-path"
      >
        <p class="modal-path-text mr-1">
          {{ data.prefix.replaceAll("/", " / ") }}
        </p>
        <input
          @input="data.name = $event.target.value"
          type="text"
          name="name"
          id="name"
          :value="data.name"
          class="modal-path-input"
          :class="[data.name ? '' : 'invalid']"
          :placeholder="$t('custom_conf_modal_placeholder')"
          :disabled="data.isReadOnly"
          pattern="^(?=.*[a-zA-Z0-9]).{1,}$"
          required
        />
        <p class="ml-1 modal-path-text">{{ $t("custom_conf_dot_conf") }}</p>
      </div>

      <!-- editor-->
      <div v-if="props.type === 'file'" class="relative">
        <div
          v-if="!data.value"
          class="absolute w-full h-full border-2 border-red-500 z-100 pointer-events-none outline-red-500"
        ></div>
        <div
          :aria-description="$t('custom_conf_modal_editor_desc')"
          id="editor"
          class="modal-editor z-10"
        ></div>
      </div>

      <!-- editor-->
      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          aria-controls="file-manager-modal"
          :aria-expanded="props.isOpen ? 'true' : 'false'"
          size="lg"
          @click="$emit('close')"
          class="btn-close text-xs"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          :disabled="!data.name || !data.value ? true : false"
          @click="sendData()"
          size="lg"
          v-if="props.action !== 'view'"
          :class="[
            props.action === 'create'
              ? 'btn-valid'
              : props.action
                ? `btn-${props.action}`
                : '',
          ]"
          class="text-xs ml-2"
        >
          {{ $t(`action_${props.action}`) }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
