<script setup>
import { reactive, defineProps, markRaw, computed } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import InstanceSvgPing from "@components/Instance/Svg/Ping.vue";
import InstanceSvgDelete from "@components/Instance/Svg/Delete.vue";
import { contentIndex } from "@utils/tabindex.js";
import { useModalStore } from "@store/instances.js";
import { useRefreshStore, useFeedbackStore } from "@store/global.js";
import { fetchAPI } from "@utils/api.js";

// Refresh when related btn is clicked
const refreshStore = useRefreshStore();
const feedbackStore = useFeedbackStore();
const modalStore = useModalStore();

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
    props.status === "up" ? [actions.stop, actions.reload] : [],
  ),

  checks: computed(() =>
    props.status === "up"
      ? props.method === "static"
        ? [topActions.ping]
        : [topActions.delete, topActions.ping]
      : [],
  ),
});

const instActions = reactive({
  isPend: false,
  isErr: false,
  data: [],
});

async function actionInstance(operation) {
  // Case delete, open confirm modal
  if (operation === "delete") {
    modalStore.data = {
      hostname: props.hostname,
    };
    return (modalStore.isOpen = true);
  }
  // Else directly send action
  await fetchAPI(
    `/api/instances/${props.hostname}/${operation}?method=ui`,
    "POST",
    null,
    instActions,
    feedbackStore.addFeedback,
  ).then((res) => {
    if (res.type === "success") {
      refreshStore.refresh();
    }
  });
}
</script>

<template>
  <div class="card-instance-container h-max">
    <div class="w-full relative">
      <div class="grid grid-cols-12 items-center">
        <div class="col-span-10 flex items-center">
          <div
            role="img"
            :aria-describedby="`${props.serverName}-instance-status`"
            :class="[props.status === 'up' ? 'bg-green-500' : 'bg-red-500']"
            class="h-4 w-4 rounded-full"
          ></div>
          <p :id="`${props.serverName}-instance-status`" class="sr-only">
            {{
              props.status === "up"
                ? $t(`instances_active`)
                : $t(`instances_inactive`)
            }}
          </p>
          <h5 class="card-instance-title">
            {{ props.serverName }}
          </h5>
        </div>
      </div>
      <div class="absolute flex flex-col justify-end items-end right-0 top-0">
        <button
          :tabindex="contentIndex"
          v-for="action in instance.checks"
          :color="action.color"
          @click="actionInstance(action.name)"
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
            {{ $t(`action_${action.name}`) }}
          </span>
        </button>
      </div>
      <div class="card-instance-info-container">
        <div v-for="item in instance.info" class="card-instance-info-item">
          <p class="card-instance-info-item-title">
            {{ $t(`instances_${item.label}`) }}
          </p>
          <p class="card-instance-info-item-content">{{ item.text }}</p>
        </div>
      </div>
      <div class="card-instance-actions-container">
        <ButtonBase
          :tabindex="contentIndex"
          v-for="action in instance.actions"
          :color="action.color"
          @click="actionInstance(action.name)"
          size="normal"
          class="text-sm mx-1 my-1 w-full xs:w-fit max-w-[200px]"
        >
          {{ $t(`action_${action.name}`) }}
        </ButtonBase>
      </div>
    </div>
  </div>
</template>
