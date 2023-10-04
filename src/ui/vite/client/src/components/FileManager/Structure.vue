<script setup>
import FileManagerModal from "@components/FileManager/Modal.vue";
import FileManagerActions from "@components/FileManager/Actions.vue";
import FileManagerBreadcrumb from "@components/FileManager/breadcrumb.vue";
import FileManagerContainer from "@components/FileManager/Container.vue";
import FileManagerItemBase from "@components/FileManager/Item/Base.vue";
import CardBase from "@components/Card/Base.vue";
import { reactive, watch } from "vue";

const props = defineProps({
  config: {
    type: Array,
  },
});

const emits = defineEmits(["updateFile"]);

// All forders need a path with children items inside it
// When a breadcrumb element or folder is clicked
// We update currPath and display the folder.path that match currPath
const path = reactive({
  current: props.config[0]["path"],
  canCreateFile: props.config[0]["canCreateFile"],
});

// Data needed for modal element, setup when an action is clicked on item (emit)
const modal = reactive({
  isOpen: false,
  type: "",
  action: "",
  path: "",
  value: "",
});

// When dropdown action is clicked on item (view, delete...)
// Action emit with the clicked action value
// We update data for the current item and display modal
function updateModal(type, action, path, value) {
  modal.type = type;
  modal.action = action;
  modal.path = path;
  modal.value = value;
  modal.isOpen = true;
}

// Fire when current path changed
// Get item that match current path to check values using config variable
// Allow to know if can crate folder or file whatever component changing path (bread or folder click)
watch(path, () => {
  props.config.forEach((item) => {
    if (path.current === item.path) {
      path.canCreateFile = item.canCreateFile;
    }
  });
});
</script>

<template>
  <div class="col-span-12">
    <CardBase>
      <div
        class="!min-h-[400px] w-full col-span-12 flex flex-col h-full justify-between"
      >
        <FileManagerBreadcrumb
          :currPath="path.current"
          @updatePath="(v) => (path.current = v)"
        />
        <FileManagerContainer
          v-for="(folder, folderID) in props.config"
          :key="folderID"
          :path="folder.path"
          :currPath="path.current"
        >
          <div
            class="col-span-12 md:col-span-6 lg:col-span-6 2xl:col-span-4 3xl:col-span-3"
            v-for="(child, childID) in folder.children"
            :key="childID"
          >
            <FileManagerItemBase
              :type="child.type"
              :path="child.path"
              :pathLevel="child.pathLevel"
              :value="child.value || ''"
              :canDelete="child.canDelete"
              :canEdit="child.canEdit"
              :canCreateFile="child.canCreateFile || false"
              :canDownload="child.canDownload || false"
              @updatePath="(v) => (path.current = v)"
              @action="
                (v) => updateModal(child.type, v, child.path, child.value || '')
              "
            />
          </div>
        </FileManagerContainer>
        <FileManagerActions
          @createFile="
            () => updateModal('file', 'create', `${path.current}/`, '')
          "
          :canCreateFile="path.canCreateFile"
        />
      </div>
    </CardBase>
    <FileManagerModal
      :aria-hidden="modal.isOpen ? 'false' : 'true'"
      v-if="modal.isOpen"
      :type="modal.type"
      :action="modal.action"
      :path="modal.path"
      :value="modal.value"
      @close="modal.isOpen = false"
      @updateFile="emits('updateFile')"
    />
  </div>
</template>
