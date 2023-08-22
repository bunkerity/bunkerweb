<script setup>
const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  serverName: {
    type: String,
    required: true,
  },
  hostname: {
    type: String,
    required: true,
  },
  type: {
    type: String,
    required: true,
  },
  health: {
    type: Boolean,
    required: true,
  },
});

const instance = reactive({
  // Info list to render
  info: [{ label: "hostname", text: props.hostname }],
});

const emits = defineEmits(["action", "delete"]);
</script>

<template>
  <div class="card-instance-container h-max">
    <form @submit.prevent class="w-full" method="POST">
      <input type="hidden" name="csrf_token" :value="props.csrfToken" />
      <div class="grid grid-cols-12 items-center">
        <div class="col-span-10 flex items-center">
          <div
            :class="[props.health ? 'bg-green-500' : 'bg-red-500']"
            class="h-4 w-4 rounded-full"
          ></div>
          <h5 class="card-instance-title">
            {{ props.serverName + "fesfesfesfesfesfefesfesfes" }}
          </h5>
        </div>
        <div class="col-span-2 flex justify-end">
          <button
            @click="$emit('delete', props.hostname)"
            class="hover:brightness-95 dark:hover:brightness-90 ml-2 rounded-full p-1 bg-red-500 scale-90"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke-width="1.5"
              stroke="currentColor"
              class="pointer-events-none w-6 h-6 stroke-white fill-red-500"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
              />
            </svg>
          </button>
        </div>
      </div>
      <div class="card-instance-info-container">
        <div v-for="item in instance.info" class="card-instance-info-item">
          <p class="card-instance-info-item-title">{{ item.label }}</p>
          <p class="card-instance-info-item-content">{{ item.text }}</p>
        </div>
      </div>
      <div class="card-instance-actions-container">
        <button
          @click="
            $emit('action', {
              hostname: props.hostname,
              operation: props.type === 'local' ? 'restart' : 'reload',
            })
          "
          v-if="props.health"
          name="operation"
          :value="props.type === 'local' ? 'restart' : 'reload'"
          class="edit-btn mx-1 text-xs"
        >
          {{ props.type === "local" ? "restart" : "reload" }}
        </button>
        <button
          @click="
            $emit('action', {
              hostname: props.hostname,
              operation: props.health ? 'stop' : 'start',
            })
          "
          name="operation"
          :value="props.health ? 'stop' : 'start'"
          :class="['mx-1 text-xs', props.health ? 'delete-btn' : 'valid-btn']"
        >
          {{ props.health ? "stop" : "start" }}
        </button>
      </div>
    </form>
  </div>
</template>
