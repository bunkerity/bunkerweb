<script setup>
import { defineProps, defineEmits } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
import JobsSvgState from "@components/Jobs/Svg/State.vue";
import ListBase from "@components/List/Base.vue";
import ListItem from "@components/List/Item.vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { computed, reactive } from "vue";

const feedbackStore = useFeedbackStore();

// Open after instance delete action is fired
const props = defineProps({
  // File or folder
  pluginId: {
    type: String,
    required: true,
  },
  pluginName: {
    type: String,
    required: true,
  },
  pluginDesc: {
    type: String,
    required: true,
  },
  isOpen: {
    type: Boolean,
    required: true,
  },
});

const delPlugin = reactive({
  isErr: false,
  isPend: false,
  data: [],
});

async function pluginDelete() {
  await fetchAPI(
    `/api/plugins/${props.pluginId}?method=ui`,
    "DELETE",
    null,
    delPlugin,
    feedbackStore.addFeedback
  ).then((res) => {
    if (res.type === "error") return;
    // Case succeed, delete items from UI
    // And emit add event to refetch ban list
    emits("pluginDelete");
    emits("close");
  });
}

const emits = defineEmits(["pluginDelete", "close"]);
</script>
<template>
  <ModalBase
    @backdrop="$emit('close')"
    :title="`Delete plugin ${props.pluginName} ?`"
    v-if="props.isOpen"
  >
    <div class="col-span-12 overflow-x-auto overflow-y-hidden">
      <p>Are you sure to delete plugin : {{ props.pluginName }}</p>
      <p>{{ props.pluginDesc }}</p>
    </div>

    <div class="w-full mt-2">
      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          color="close"
          size="lg"
          @click="$emit('close')"
          type="button"
          class="text-xs"
        >
          Close
        </ButtonBase>
        <ButtonBase
          color="delete"
          size="lg"
          @click="pluginDelete()"
          type="button"
          class="text-xs"
        >
          Delete
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
