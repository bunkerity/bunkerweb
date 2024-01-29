<script setup>
import { ref, reactive } from "vue";
import SettingsUploadSvgSuccess from "@components/Settings/Upload/Svg/Success.vue";
import SettingsUploadFeedback from "@components/Settings/Upload/Feedback.vue";
import { contentIndex } from "@utils/tabindex.js";

const props = defineProps({
  tabId: {
    type: [String, Number],
    required: false,
  },
});

const dropzone = reactive({
  isDragOn: false,
  files: [],
  count: 0,
});

function delFileFromList(v) {
  const filterArr = dropzone.files.filter((item) => item.date !== v.date);
  dropzone.files = filterArr;
}

const fileInp = ref();

function addFile(e) {
  dropzone.isDragOn = false;
  fileInp.files = e.dataTransfer.files;
  const timeout = 500;
  for (let i = 0; i < fileInp.files.length; i++) {
    setTimeout(() => uploadFile(fileInp.files[i]), timeout * i);
  }
}

function uploadFiles(files) {
  const timeout = 500;
  for (let i = 0; i < files.length; i++) {
    setTimeout(() => this.uploadFile(files[i]), timeout * i);
  }
}

function uploadFile(file) {
  const date = Date.now();
  let name = file.name;
  if (name.length >= 12) {
    let splitName = name.split(".");
    name = splitName[0].substring(0, 13) + "... ." + splitName[1];
  }

  let xhr = new XMLHttpRequest();
  xhr.open("POST", "plugins/upload");
  let fileSize;

  xhr.upload.addEventListener("progress", ({ loaded, total }) => {
    let fileTotal = Math.floor(total / 1000);

    fileTotal < 1024
      ? (fileSize = fileTotal + " KB")
      : (fileSize = (loaded / (1024 * 1024)).toFixed(2) + " MB");

    dropzone.files.push({
      name: name,
      fileSize: fileSize,
      state: "upload",
      date: date,
    });
  });

  xhr.addEventListener("readystatechange", () => {
    // Upload end

    if (xhr.readyState === XMLHttpRequest.DONE) {
      //Remove from upload array
      const currID = dropzone.files.findIndex(
        (item) =>
          item.name === name &&
          item.fileSize === fileSize &&
          item.state === "upload" &&
          item.date === date,
      );

      if (xhr.status == 201) {
        dropzone.files[currID].state = "success";
      } else {
        dropzone.files[currID].state = "fail";
      }
    }
  });

  const data = new FormData();
  data.set("file", file);
  xhr.send(data);
}
</script>

<template>
  <div class="m-2 mt-6 p-0 col-span-12 grid grid-cols-12">
    <!-- dropzone -->
    <button
      :tabindex="props.tabId || contentIndex"
      id="dropzone-form"
      method="POST"
      @click="fileInp.click()"
      @drop.prevent="(e) => addFile(e)"
      @dragover.prevent="dropzone.isDragOn = true"
      @dragend.prevent="dropzone.isDragOn = false"
      @dragleave.prevent="dropzone.isDragOn = false"
      :class="[
        dropzone.isDragOn
          ? 'border-solid bg-gray-100 dark:bg-slate-700/50'
          : 'border-dashed',
      ]"
      class="hover:bg-gray-100 dark:hover:bg-slate-700/50 cursor-pointer col-span-12 border-2 rounded-lg p-2 border-primary dark:brightness-125 drop-zone"
    >
      <input
        tabindex="-1"
        @change="uploadFiles(fileInp.files)"
        ref="fileInp"
        type="file"
        name="file"
        multiple="multiple"
        class="hidden"
      />
      <i class="fa-solid fa-cloud-upload-alt"></i>
      <p class="dark:text-gray-500 text-sm text-center my-3">
        {{ $t("inp_upload_add") }}
      </p>
    </button>
    <div class="col-span-12">
      <SettingsUploadFeedback
        v-for="item in dropzone.files"
        :name="item.name"
        :fileSize="item.fileSize"
        :state="item.state"
        :date="item.date"
        @close="(v) => delFileFromList(v)"
      />
    </div>
    <!-- end dropzone -->

    <div class="col-span-12 flex flex-col justify-center items-center mt-4">
      <hr class="line-separator z-10 w-full" />
      <p class="dark:text-gray-500 text-xs text-center mt-1 mb-2">
        <span class="mx-0.5">
          <SettingsUploadSvgSuccess class="scale-90" />
        </span>
        {{ $t("inp_upload_warning") }}
      </p>
    </div>
  </div>
</template>
