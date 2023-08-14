<script setup>
// Format working with file manager
const config = [
  {
    type: "folder",
    path: "root",
    canDelete: false,
    canEdit: false,
    canCreateFile: false,
    children: [
      {
        type: "folder",
        path: "root/folder_name",
        canDelete: false,
        canEdit: false,
        canCreateFile: true,
      },
      {
        type: "file",
        path: "root/file1",
        canDelete: false,
        canEdit: false,
        canDownload: false,
      },
    ],
  },
  {
    type: "folder",
    path: "root/folder_name",
    canDelete: false,
    canEdit: false,
    canCreateFile: true,
    children: [
      {
        type: "folder",
        path: "root/folder_name/folder_nest_name",
        canDelete: false,
        canEdit: false,
      },
      {
        type: "file",
        path: "root/folder_name/folder_nest_namefesfsefesfesfesfesfesfesfes",
        canDelete: false,
        canEdit: false,
        canDownload: false,
      },
    ],
  },
  {
    type: "folder",
    path: "root/folder_name/folder_nest_name",
    canDelete: false,
    canEdit: false,
    canCreateFile: false,

    children: [
      {
        type: "file",
        path: "root/folder_name/folder_nest_name/file",
        canDelete: false,
        canEdit: true,
        canDownload: false,
      },
    ],
  },
];

// All forders need a path with children items inside it
// When a breadcrumb element or folder is clicked
// We update currPath and display the folder.path that match currPath
const path = reactive({
  current: config[0]["path"],
  canCreateFile: config[0]["canCreateFile"],
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
// Allow to know canCreateFile whatever component changing path (bread or folder click)
watch(
  () => path.current,
  () => {
    path.canCreateFile = config.find(
      (item) => item.path === path.current
    ).canCreateFile;
  }
);
</script>

<template>
  <div class="w-full bg-white grid-cols-12">
    <FileManagerBreadcrumb
      :currPath="path.current"
      @updatePath="(v) => (path.current = v)"
    />
    <FileManagerContainer
      v-for="folder in config"
      :path="folder.path"
      :currPath="path.current"
    >
      <div v-for="child in folder.children">
        <FileManagerItemBase
          :type="child.type"
          :path="child.path"
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
      @createFile="() => updateModal('file', 'create', `${path.current}/`, '')"
      :canCreateFile="path.canCreateFile"
    />
    <FileManagerModal
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
