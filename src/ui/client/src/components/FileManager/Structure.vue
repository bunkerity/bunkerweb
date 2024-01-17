<script setup>
import FileManagerModal from "@components/FileManager/Modal.vue";
import FileManagerActions from "@components/FileManager/Actions.vue";
import FileManagerBreadcrumb from "@components/FileManager/Breadcrumb.vue";
import FileManagerContainer from "@components/FileManager/Container.vue";
import FileManagerItemBase from "@components/FileManager/Item/Base.vue";
import CardBase from "@components/Card/Base.vue";
import { reactive, watch } from "vue";
import { useModalStore } from "@store/configs.js";

const modalStore = useModalStore();

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
  current: "root", // when mount or render, always be on root
  canCreateFile: props.config[0]["canCreateFile"],
});

// Fire when current path changed
// Get item that match current path to check values using config variable
// Allow to know if can create folder or file whatever component changing path (bread or folder click)
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
              :data="{
                type: child.type,
                path: child.path,
                pathLevel: child.pathLevel,
                value: child.value || '',
              }"
              :rights="{
                canDelete: child.canDelete,
                canEdit: child.canEdit,
                canCreateFile: child.canCreateFile || false,
                canDownload: child.canDownload || false,
              }"
              @updatePath="(v) => (path.current = v)"
            />
          </div>
        </FileManagerContainer>
        <FileManagerActions
          @createFile="
            () => {
              modalStore.setData({
                type: 'file',
                action: 'create',
                path: `${path.current}/`,
                data: '',
                method: 'ui',
              });
              modalStore.setOpen(true);
            }
          "
          :canCreateFile="path.canCreateFile"
        />
      </div>
    </CardBase>
    <FileManagerModal
      :aria-hidden="modalStore.isOpen ? 'false' : 'true'"
      @updateFile="
        () => {
          emits('updateFile');
          path.current = 'root';
        }
      "
    />
  </div>
</template>
