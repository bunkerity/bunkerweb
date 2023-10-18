<script setup>
import ButtonBase from "@components/Button/Base.vue";
import { reactive, defineProps, defineEmits, markRaw, computed } from "vue";
import InstanceSvgPing from "@components/Instance/Svg/Ping.vue";
import InstanceSvgDelete from "@components/Instance/Svg/Delete.vue";

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
  method: {
    type: String,
    required: true,
  },
  port: {
    type: Number,
    required: true,
  },
  status: {
    type: String,
    required: true,
  },
});

const actions = reactive({
  stop: { name: "stop", color: "delete" },
  reload: { name: "reload", color: "edit" },
  restart: { name: "restart", color: "valid" },
});

const topActions = reactive({
  delete: {
    name: "delete",
    class: "bg-red-500",
    svg: markRaw(InstanceSvgDelete),
    popup: false,
    emit: "delete",
  },
  ping: {
    name: "ping",
    class: "bg-sky-500",
    svg: markRaw(InstanceSvgPing),
    popup: false,
    emit: "action",
  },
});

const instance = reactive({
  // Info list to render
  info: [
    { label: "hostname", text: props.hostname },
    { label: "method", text: props.method },
    { label: "port", text: props.port },
  ],

  actions: computed(() =>
    props.status === "up"
      ? [actions.stop, actions.reload, actions.restart]
      : [actions.reload, actions.restart]
  ),
  checks: computed(() =>
    props.method === "static"
      ? [topActions.delete, topActions.ping]
      : [topActions.ping]
  ),
});

// action => return action to execute with instance name
// delete => return instance name to delete
const emits = defineEmits(["action", "delete"]);
</script>

<template>
  <div class="card-instance-container h-max">
    <div class="w-full relative">
      <input type="hidden" name="csrf_token" :value="props.csrfToken" />
      <div class="grid grid-cols-12 items-center">
        <div class="col-span-10 flex items-center">
          <div
            :class="[props.status === 'up' ? 'bg-green-500' : 'bg-red-500']"
            class="h-4 w-4 rounded-full"
          ></div>
          <h5 class="card-instance-title">
            {{ props.serverName }}
          </h5>
        </div>
      </div>
      <div class="absolute flex flex-col justify-end items-end right-0 top-0">
        <button
          v-for="action in instance.checks"
          :color="action.color"
          @click="
            $emit(
              action.emit,
              action.emit === 'action'
                ? {
                    hostname: props.hostname,
                    operation: action.name,
                  }
                : props.hostname
            )
          "
          @pointerover="action.popup = true"
          @pointerleave="action.popup = false"
          :class="[action.popup ? 'pl-2 p-1' : 'w-10 p-1', `${action.class}`]"
          class="h-10 hover:brightness-95 dark:hover:brightness-90 ml-2 my-1 rounded-full p-1 scale-90"
        >
          <component :is="action.svg"></component>
          <span
            class="text-normal font-normal mx-1 mr-2 text-white whitespace-nowrap"
            v-show="action.popup"
          >
            {{ action.name }}
          </span>
        </button>
      </div>
      <div class="card-instance-info-container">
        <div v-for="item in instance.info" class="card-instance-info-item">
          <p class="card-instance-info-item-title">{{ item.label }}</p>
          <p class="card-instance-info-item-content">{{ item.text }}</p>
        </div>
      </div>
      <div class="card-instance-actions-container">
        <ButtonBase
          v-for="action in instance.actions"
          :color="action.color"
          @click="
            $emit('action', {
              hostname: props.hostname,
              operation: action.name,
            })
          "
          size="normal"
          class="text-sm mx-1 my-1 w-full xs:w-fit max-w-[200px]"
        >
          {{ action.name }}
        </ButtonBase>
      </div>
    </div>
  </div>
</template>
