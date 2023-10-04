<script setup>
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

const emits = defineEmits(["close"]);
</script>
<template>
  <div class="modal-container">
    <div class="modal-wrap">
      <div class="modal-card">
        <div class="w-full flex justify-between">
          <p class="modal-card-title">
            {{ `${props.action} ${props.type}` }}
          </p>
        </div>
        <form class="w-full" id="form-services" method="POST">
          <div class="modal-path">
            <p class="modal-path-text">
              {{ prefix }}
            </p>
            <input
              type="text"
              name="name"
              id="name"
              :value="oldName"
              class="modal-input"
              placeholder="path"
              :disabled="props.action === 'view'"
              required
            />
            <p v-if="props.type === 'file'" class="ml-1 modal-path-text">
              .conf
            </p>
          </div>
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
          <input
            type="hidden"
            id="operation"
            :value="props.action"
            name="operation"
          />
          <input type="hidden" id="path" :value="props.path" name="path" />
          <input type="hidden" id="old_name" :value="oldName" name="old_name" />
          <input type="hidden" id="_type" :value="props.type" name="type" />
          <textarea class="hidden" id="content" name="content"></textarea>
          <!-- editor-->
          <div v-if="props.type === 'file'" id="editor" class="modal-editor">
            {{ props.value }}
          </div>
          <!-- editor-->

          <div class="mt-2 w-full justify-end flex">
            <button
              @click="$emit('close')"
              type="button"
              class="close-btn text-xs"
            >
              Close
            </button>
            <button
              v-if="props.action !== 'view'"
              type="submit"
              :class="[
                props.action === 'edit' ? 'edit-btn' : '',
                props.action === 'download' ? 'download-btn' : '',
                props.action === 'delete' ? 'delete-btn' : '',
                props.action === 'create' ? 'valid-btn' : '',
              ]"
              class="text-xs ml-2"
            >
              {{ props.action }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
