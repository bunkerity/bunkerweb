<script setup>
import { reactive, computed, defineProps, defineEmits } from "vue";
import FileManagerItemDropdown from "@components/FileManager/Item/Dropdown.vue";
import FileManagerItemSvgFolder from "@components/FileManager/Item/Svg/Folder.vue";
import FileManagerItemSvgFile from "@components/FileManager/Item/Svg/File.vue";
import { contentIndex } from "@utils/tabindex.js";
import { useModalStore } from "@store/configs.js";

const modalStore = useModalStore();

// FileManagerBase can be a folder or file
// Case folder, emit the folder path on click to update display
// Emit on filemanager layout the value of buttons list @action
const props = defineProps({
  data: {
    type: Object,
    required: true,
  },
  rights: {
    type: Object,
    required: true,
  },
});

// Check if root path (not same svg) by slash numbers
const path = reactive({
  name: props.data.path.substring(props.data.path.lastIndexOf("/") + 1),
});

const itemID = computed(() => {
  return `${props.data.path}-${props.data.pathLevel}-${path.name.replaceAll(
    "_",
    "-"
  )}`;
});

function runAction(action) {
  const data = props.data;
  data.action = action;
  modalStore.setData(data);
  modalStore.setOpen(true);
}

const emits = defineEmits(["updatePath"]);
</script>

<template>
  <div class="file-manager-item-container">
    <button
      :tabindex="modalStore.isOpen ? '-1' : contentIndex"
      class="file-manager-item-nav"
      @click="
        props.data.type === 'folder'
          ? $emit('updatePath', props.data.path)
          : runAction('view')
      "
      :aria-describedby="`${itemID}-text`"
    >
      <span class="sr-only" :id="`${itemID}-text`">
        {{ $t("custom_conf_path") }}
      </span>
      <FileManagerItemSvgFolder
        v-if="props.data.type === 'folder'"
        :path="props.data.path"
      />

      <FileManagerItemSvgFile v-if="props.data.type === 'file'" />

      <span
        :class="[
          path.name.length > 50 ? 'xs' : path.name.length > 50 ? 'sm' : 'base',
        ]"
        class="file-manager-item-name"
      >
        {{
          props.data.pathLevel === 1
            ? path.name.replaceAll("_", "-")
            : path.name
        }}
      </span>
    </button>
    <FileManagerItemDropdown
      :id="itemID"
      :rights="props.rights"
      :data="props.data"
    />
  </div>
</template>
