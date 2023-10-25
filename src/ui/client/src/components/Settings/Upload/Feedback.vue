<script setup>
import SettingsUploadSvgUpload from "@components/Settings/Upload/Svg/Upload.vue";
import SettingsUploadSvgError from "@components/Settings/Upload/Svg/Error.vue";
import SettingsUploadSvgSuccess from "@components/Settings/Upload/Svg/Success.vue";
import SettingsUploadSvgDot from "@components/Settings/Upload/Svg/Dot.vue";
import SettingsUploadSvgCross from "@components/Settings/Upload/Svg/Cross.vue";
import { defineEmits, defineProps } from "vue";

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  fileSize: {
    type: String || Number,
    required: true,
  },
  // upload || success || fail
  state: {
    type: String,
    required: true,
  },
  date: {
    type: Number,
    required: true,
  },
});

const emits = defineEmits(["close"]);
</script>

<template>
  <div class="mt-2 rounded p-2 w-full bg-gray-100 dark:bg-gray-800">
    <div class="flex items-center justify-between">
      <SettingsUploadSvgUpload v-if="props.state === 'upload'" />
      <SettingsUploadSvgError v-if="props.state === 'fail'" />
      <SettingsUploadSvgSuccess v-if="props.state === 'success'" />

      <span class="text-sm text-slate-700 dark:text-gray-300 mr-4"
        >{{ props.name }}
      </span>
      <span class="text-sm text-slate-700 dark:text-gray-300">
        {{ props.fileSize }}
      </span>
      <SettingsUploadSvgDot v-if="props.state === 'upload'" />

      <button
        class="pl-1 -translate-y-0.5"
        v-if="props.state === 'fail' || props.state === 'success'"
        @click="
          $emit('close', {
            name: props.name,
            fileSize: props.fileSize,
            state: props.state,
            date: props.date,
          })
        "
      >
        <SettingsUploadSvgCross />
      </button>
    </div>
  </div>
</template>
