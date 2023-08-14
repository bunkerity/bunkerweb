<script setup>
const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  hostname: {
    type: String,
    required: true,
  },
  _type: {
    type: String,
    required: true,
  },
  health: {
    type: Boolean,
    required: true,
  },
  csrfToken: {
    type: String,
    required: true,
  },
});

const instance = reactive({
  // Info list to render
  info: [
    { label: "type", text: props._type },
    { label: "hostname", text: props.hostname },
  ],
});
</script>

<template>
  <div class="card-instance-container h-max">
    <form class="w-full" :id="`form-instance-${props.id}`" method="POST">
      <input type="hidden" name="csrf_token" :value="props.csrfToken" />
      <input type="hidden" name="INSTANCE_ID" :value="props.id" />
      <div class="flex items-center">
        <div
          :class="[props.health ? 'bg-green-500' : 'bg-red-500']"
          class="h-4 w-4 rounded-full"
        ></div>
        <h5 class="card-instance-title">
          {{ props.name ? props.name : "none" }}
        </h5>
      </div>
      <div class="card-instance-info-container">
        <div v-for="item in instance.info" class="card-instance-info-item">
          <p class="card-instance-info-item-title">{{ item.label }}</p>
          <p class="card-instance-info-item-content">{{ item.text }}</p>
        </div>
      </div>
      <div class="card-instance-actions-container">
        <button
          v-if="props.health"
          type="submit"
          name="operation"
          :value="props._type === 'local' ? 'restart' : 'reload'"
          class="edit-btn mx-1 text-xs"
        >
          {{ props._type === "local" ? "restart" : "reload" }}
        </button>
        <button
          type="submit"
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
