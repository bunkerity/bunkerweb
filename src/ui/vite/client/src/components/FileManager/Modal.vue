<script setup>
import { computed, defineProps, defineEmits, reactive } from "vue";
import ModalBase from "@components/Modal/Base.vue";
import ButtonBase from "@components/Button/Base.vue";

// Open after a file manager item (folder / file) action is clicked
// With the current folder / file data
// Update name or content file if wanted
const props = defineProps({
  // File or folder
  type: {
    type: String,
    required: true,
  },
  // view || edit || download || delete
  action: {
    type: String,
    required: true,
  },
  // Current item path
  path: {
    type: String,
    required: true,
  },
  // File value is shown with an editor
  value: {
    type: String,
    required: true,
  },
});

// Filter data from path
const oldName = computed(() => {
  return props.path.split("/")[props.path.split("/").length - 1];
});

const prefix = computed(() => {
  const arr = props.path.split("/");
  arr.pop();
  return `${arr.join("/")}/`;
});

const inp = reactive({
  name: "",
});

const emits = defineEmits(["create", "close"]);
</script>
<template>
  <ModalBase :title="`${props.action} ${props.type}`">
    <div class="w-full">
      <div class="modal-path">
        <p class="modal-path-text">
          {{ prefix }}
        </p>
        <input
          @input="inp.name = $event.target.value"
          ref="inpData"
          type="text"
          name="name"
          id="name"
          :value="oldName"
          class="modal-input"
          placeholder="path"
          :disabled="props.action === 'view'"
          required
        />
        <p v-if="props.type === 'file'" class="ml-1 modal-path-text">.conf</p>
      </div>

      <!-- editor-->
      <div v-if="props.type === 'file'" id="editor" class="modal-editor">
        {{ props.value }}
      </div>
      <!-- editor-->

      <div class="mt-2 w-full justify-end flex">
        <ButtonBase size="lg" @click="$emit('close')" class="btn-close text-xs">
          Close
        </ButtonBase>
        <ButtonBase
          @click="
            () => {
              if (props.type === 'folder' && !inp.name) return;
              $emit('create', {
                type: props.type,
                action: props.action,
                path: props.path,
                name: inp.name,
              });
            }
          "
          size="lg"
          v-if="props.action !== 'view'"
          :class="[
            props.action === 'edit' ? 'btn-edit' : '',
            props.action === 'download' ? 'btn-download' : '',
            props.action === 'delete' ? 'btn-delete' : '',
            props.action === 'create' ? 'btn-valid' : '',
          ]"
          class="text-xs ml-2"
        >
          {{ props.action }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
