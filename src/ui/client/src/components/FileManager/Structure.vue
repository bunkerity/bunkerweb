<script setup>
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

// All forders need a path with children items inside it
// When a breadcrumb element or folder is clicked
// We update currPath and display the folder.path that match currPath
modalStore.data.path = "root";
const path = reactive({
  canCreateFile: props.config[0]["canCreateFile"],
});

// Fire when current path changed
// Get item that match current path to check values using config variable
// Allow to know if can create folder or file whatever component changing path (bread or folder click)
watch(modalStore, () => {
  props.config.forEach((item) => {
    if (modalStore.data.path === item.path) {
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
        <FileManagerBreadcrumb />
        <FileManagerContainer
          v-for="(folder, folderID) in props.config"
          :key="folderID"
          :path="folder.path"
        >
          <div
            class="col-span-12 md:col-span-6 lg:col-span-6 2xl:col-span-4 3xl:col-span-3"
            v-for="(child, childID) in folder.children"
            :key="childID"
          >
            <FileManagerItemBase
              :data="{
                type: child.type,
                name: child.path.substring(child.path.lastIndexOf('/') + 1),
                path: child.path,
                pathLevel: child.pathLevel,
                value: child.data || '',
              }"
              :rights="{
                canDelete: child.canDelete,
                canEdit: child.canEdit,
                canCreateFile: child.canCreateFile || false,
                canDownload: child.canDownload || false,
              }"
            />
          </div>
        </FileManagerContainer>
        <FileManagerActions :canCreateFile="path.canCreateFile" />
      </div>
    </CardBase>
  </div>
</template>
