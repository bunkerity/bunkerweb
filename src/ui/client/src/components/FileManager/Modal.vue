<script setup>
import {
  computed,
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
import { contentIndex } from "@utils/tabindex.js";
import { useFeedbackStore } from "@store/global.js";
import { useModalStore } from "@store/configs.js";
import { useRefreshStore } from "@store/global.js";

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();

const modalStore = useModalStore();
const feedbackStore = useFeedbackStore();

// Filter data from path

const data = reactive({
  oldName: "",
  name: "",
  value: "",
  path: "",
  isReadOnly: computed(() => {
    if (modalStore.data.type !== "file") return true;
    if (
      modalStore.data.action.toLowerCase() === "view" ||
      modalStore.data.action.toLowerCase() === "delete"
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

function setDataFromStore() {
  data.oldName = modalStore.data.name;
  data.name = modalStore.data.name;
  data.value = modalStore.data.value;
  data.path = modalStore.data.path;
}

let editor = null;

// Use ace editor
onMounted(() => {
  setDataFromStore();
  // default value
  if (modalStore.data.type !== "file") return;
  editor = new FileEditor();
  editor.setValue(data.value);
  editor.readOnlyBool(data.isReadOnly);
  editor.editor.on("change", () => {
    data.value = editor.getValue();
  });
});

onBeforeUpdate(() => {
  setDataFromStore();
  try {
    editor.destroy();
  } catch (err) {}
});

onUpdated(() => {
  // default value
  if (modalStore.data.type !== "file") return;
  editor = new FileEditor();
  editor.setValue(modalStore.data.value);
  editor.readOnlyBool(data.isReadOnly);
  editor.editor.on("change", () => {
    data.value = editor.getValue();
  });
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
  const splitPath = modalStore.data.path
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
    method: "ui",
  };

  return conf;
}

async function sendData() {
  // Send only if filename and content
  if (!data.name && !data.value) return;

  // Case all needed data
  const conf = formatData();
  const method =
    modalStore.data.action.toLowerCase() === "delete" ? "DELETE" : "PUT";
  const baseURL = `/api/custom_configs${
    method === "DELETE" ? `/${conf.old_name}` : ``
  }`;
  const queries =
    modalStore.data.action.toLowerCase() === "delete"
      ? `?method=ui&custom_config_name=${conf.old_name}&config_type=${conf.type}&service_id=${conf.service_id}`
      : `?method=ui`;
  const api = `${baseURL}${queries}`;
  // Fetch
  await fetchAPI(
    api,
    method,
    modalStore.data.action.toLowerCase() === "delete" ? null : conf,
    updateConf,
    feedbackStore.addFeedback,
  )
    .then((res) => {
      // Case saved, close modal, go to root path and refresh
      if (res.type === "success") {
        modalStore.$reset();
        modalStore.isOpen = false;
        refreshStore.refresh();
        return;
      }
    })
    .catch((err) => {});
}

const emits = defineEmits(["close"]);
</script>
<template>
  <ModalBase
    v-show="modalStore.isOpen"
    :aria-hidden="modalStore.isOpen ? 'false' : 'true'"
    id="file-manager-modal"
    @backdrop="$emit('close')"
    :title="
      $t('custom_conf_modal_title', {
        action: $t(`action_${modalStore.data.action}`),
      })
    "
  >
    <div class="w-full">
      <div
        role="group"
        :aria-description="$t('custom_conf_modal_path_desc')"
        class="modal-path"
      >
        <p class="modal-path-text mr-1">
          {{ modalStore.data.path.replaceAll("/", " / ") + " /" }}
        </p>
        <input
          :tabindex="modalStore.isOpen ? contentIndex : '-1'"
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
      <div v-if="modalStore.data.type === 'file'" class="relative">
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
          :tabindex="modalStore.isOpen ? contentIndex : '-1'"
          aria-controls="file-manager-modal"
          :aria-expanded="modalStore.isOpen ? 'true' : 'false'"
          size="lg"
          @click="modalStore.isOpen = false"
          class="btn-close text-xs"
        >
          {{ $t("action_close") }}
        </ButtonBase>
        <ButtonBase
          :tabindex="modalStore.isOpen ? contentIndex : '-1'"
          :disabled="!data.name || !data.value ? true : false"
          @click="sendData()"
          size="lg"
          v-if="modalStore.data.action !== 'view'"
          :class="[
            modalStore.data.action === 'create'
              ? 'btn-valid'
              : modalStore.data.action
                ? `btn-${modalStore.data.action}`
                : '',
          ]"
          class="text-xs ml-2"
        >
          {{ $t(`action_${modalStore.data.action}`) }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
