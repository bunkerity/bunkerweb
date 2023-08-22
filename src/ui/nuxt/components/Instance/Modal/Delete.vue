<script setup>
// Open after instance delete action is fired
const props = defineProps({
  // File or folder
  hostname: {
    type: String,
    required: true,
  },
  isOpen: {
    type: Boolean,
    required: true,
  },
});

const emits = defineEmits(["close", "delete"]);
</script>
<template>
  <div v-if="props.isOpen" class="modal-container">
    <div class="modal-wrap">
      <div class="modal-card">
        <div class="w-full flex justify-between">
          <p class="modal-card-title">DELETE INSTANCE</p>
        </div>
        <form @submit.prevent class="w-full" method="POST">
          <div class="flex justify-center">
            <div class="modal-path">
              <p class="modal-path-text">
                {{
                  `Are you sure to delete instance with hostname ${props.hostname} ?`
                }}
              </p>
            </div>
          </div>
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />

          <div class="mt-2 w-full justify-end flex">
            <button
              @click="$emit('close')"
              type="button"
              class="close-btn text-xs"
            >
              Close
            </button>
            <button
              @click="
                () => {
                  $emit('close');
                  $emit('delete', { hostname: props.hostname });
                }
              "
              class="delete-btn text-xs ml-2"
            >
              DELETE
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
