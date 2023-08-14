<script setup>
// Format working with file manager
const config = [
  {
    type: "folder",
    path: "root",
    canDelete: false,
    canEdit: false,
    children: [
      {
        type: "folder",
        path: "root/folder_name",
        canDelete: false,
        canEdit: false,
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

// All forders need a path with children that are items inside it
// When a breadcrumb element or folder is clicked
// We update currPath and display the folder.path that match currPath
const currPath = ref(config[0]["path"]);

// Data needed for modal element, setup when an action is clicked on item
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
function updateAction(type, action, path, value) {
  modal.type = type;
  modal.action = action;
  modal.path = path;
  modal.value = value;
  modal.isOpen = true;
}
</script>

<template>
  <div class="w-full bg-white grid-cols-12">
    <FileManagerBreadcrumb
      :currPath="currPath"
      @updatePath="(v) => (currPath = v)"
    />
    <FileManagerContainer
      v-for="folder in config"
      :path="folder.path"
      :currPath="currPath"
    >
      <div v-for="child in folder.children">
        <FileManagerItemBase
          :type="child.type"
          :path="child.path"
          :value="child.value || ''"
          :canDelete="child.canDelete"
          :canEdit="child.canEdit"
          :canDownload="child.canDownload || false"
          @updatePath="(v) => (currPath = v)"
          @action="
            (v) => updateAction(child.type, v, child.path, child.value || '')
          "
        />
      </div>
    </FileManagerContainer>
    <FileManagerModal
      :aria-hidden="modal.isOpen ? 'false' : 'true'"
      v-show="modal.isOpen"
      :type="modal.type"
      :action="modal.action"
      :path="modal.path"
      :value="modal.value"
      @close="modal.isOpen = false"
    />
  </div>
</template>
