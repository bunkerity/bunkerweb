<script setup>
import FileManagerModal from "@components/FileManager/Modal.vue";
import FileManagerActions from "@components/FileManager/Actions.vue";
import FileManagerBreadcrumb from "@components/FileManager/breadcrumb.vue";
import FileManagerContainer from "@components/FileManager/Container.vue";
import FileManagerItemBase from "@components/FileManager/Item/Base.vue";
import CardBase from "@components/Card/Base.vue";
import { reactive, watch } from "vue";
import { generateItem } from "@utils/custom_configs.js";
import { useFeedbackStore } from "@store/global.js";
import { fetchAPI } from "@utils/api.js";

const props = defineProps({
  config: {
    type: Array,
  },
});

const feedbackStore = useFeedbackStore();

const config = reactive({
  data: props.config,
});

// All forders need a path with children items inside it
// When a breadcrumb element or folder is clicked
// We update currPath and display the folder.path that match currPath
const path = reactive({
  current: config.data[0]["path"],
  canCreateFile: config.data[0]["canCreateFile"],
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
  config.data.forEach((item) => {
    if (path.current === item.path) {
      path.canCreateFile = item.canCreateFile;
    }
  });
});

const updateConfigs = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function updateConfig(data) {
  await fetchAPI(
    "/api/custom_configs?method=ui",
    "PUT",
    data,
    updateConfigs,
    feedbackStore.addFeedback
  );
}

const createConfigs = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function createConfig(data) {
  await fetchAPI(
    "/api/custom_configs?method=ui",
    "POST",
    data,
    createConfigs,
    feedbackStore.addFeedback
  );
}

const deleteConfigs = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function deleteConfig(data) {
  await fetchAPI(
    "/api/custom_configs?method=ui",
    "DELETE",
    data,
    deleteConfigs,
    feedbackStore.addFeedback
  );
}

function handleCreate(data) {
  modal.isOpen = false;

  const splitPath = data.path.replace("root/", "").trim().split("/");
  !splitPath[splitPath.length - 1] ? splitPath.pop() : false;
  const type = splitPath[0].replaceAll("-", "_");
  const serviceID = splitPath[1] ? splitPath[1] : "";

  const newConf = [
    {
      service_id: serviceID,
      type: type,
      name: data.name,
      data: data.data,
    },
  ];

  if (data.action === "create") createConfig(newConf);
  if (data.action === "edit") updateConfig(newConf);
  if (data.action === "delete") deleteConfig(newConf);
}
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
          v-for="(folder, folderID) in config.data"
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
      @createFile="(v) => handleCreate(v)"
      :aria-hidden="modal.isOpen ? 'false' : 'true'"
      v-if="modal.isOpen"
      :type="modal.type"
      :action="modal.action"
      :path="modal.path"
      :value="modal.value"
      @close="modal.isOpen = false"
    />
  </div>
</template>
