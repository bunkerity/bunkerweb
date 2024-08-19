<script setup>
import Icons from "@components/Widget/Icons.vue";
import Container from "@components/Widget/Container.vue";
import Text from "@components/Widget/Text.vue";
import { reactive } from "vue";

/**
 *  @name Widget/FileManager.vue
 *  @description File manager component. Useful with cache page.
 *  @example
 *  {
 *    title: "Total Users",
 *    type: "card",
 *    titleClass: "text-lg",
 *    color : "info",
 *    tag: "h2"
 *  }
 *  @param {Object} data -  Can be a translation key or by default raw text.
 *  @param {String} [baseFolder="base"] - The base folder to display by default
 *  @param {Object} [columns={"pc": "12", "tablet": "12", "mobile": "12"}] - Work with grid system { pc: 12, tablet: 12, mobile: 12}
 *  @param {String} [containerClass=""] - Additional class
 */

const props = defineProps({
  data: {
    type: Object,
    required: true,
  },
  baseFolder: {
    type: String,
    required: false,
    default: "base",
  },
  columns: {
    type: Object,
    required: false,
    default: { pc: "12", tablet: "12", mobile: "12" },
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
});

const manager = reactive({
  currFolder: "base", // by default, base
});

/**
 *  @name changeFolder
 *  @description Change current folder to the selected one if it is a folder.
 *  @param {String} name - The name of the folder or file
 *  @param {String} type - The type of element clicked, can be a folder or a file.
 *  @returns {void}
 */
function changeFolder(name, type) {
  if (type !== "folder") return;
  manager.currFolder = name;
}

/**
 *  @name downloadCache
 *  @description Download the cache file.
 *  @param {String} fileName - The cache filename to download
 *  @returns {void}
 */
function downloadCache(fileName) {
  const url = `${location.href}${fileName}`;

  const a = document.createElement("a");
  a.href = url;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
</script>

<template>
  <Container
    data-is="file-manager"
    :containerClass="`${props.containerClass}layout-file-manager`"
    :columns="props.columns"
  >
    <div class="file-manager-breadcrumb">
      <span class="file-manager-breadcrumb-base">/</span>
      <button
        class="file-manager-breadcrumb-btn"
        @click="changeFolder(parent, 'folder')"
        v-for="parent in props.data[manager.currFolder].parents"
      >
        {{ parent }}
      </button>
    </div>
    <div class="file-manager-content">
      <template v-for="child in props.data[manager.currFolder].children">
        <button
          @click="changeFolder(child, props.data[child].type)"
          :class="[
            props.data[child].type === 'file'
              ? 'cursor-default'
              : 'cursor-pointer',
            'file-manager-btn',
          ]"
        >
          <div class="flex justify-center items-end">
            <Icons
              :iconName="
                props.data[child].type === 'file' ? 'document' : 'folder'
              "
              color="dark-darker"
            />
            <button
              class="hover:brightness-90"
              v-if="props.data[child]?.downloadEndpoint"
              @click="downloadCache(props.data[child]?.downloadEndpoint)"
            >
              <Icons iconName="download" color="info" />
            </button>
          </div>
          <Text :text="child" />
        </button>
      </template>
    </div>
  </Container>
</template>
