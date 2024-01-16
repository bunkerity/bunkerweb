<script setup>
import { defineProps, defineEmits } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
import JobsSvgState from "@components/Jobs/Svg/State.vue";
import ListBase from "@components/List/Base.vue";
import ListItem from "@components/List/Item.vue";

// Open after instance delete action is fired
const props = defineProps({
  // File or folder
  history: {
    type: Array,
    required: true,
  },
  jobName: {
    type: String,
    required: true,
  },
  isOpen: {
    type: Boolean,
    required: true,
  },
});

const positions = ["col-span-2", "col-span-5", "col-span-5"];

const emits = defineEmits(["close"]);
</script>
<template>
  <ModalBase
    :id="`history-modal-${props.jobName}`"
    :aria-hidden="props.isOpen ? 'false' : 'true'"
    @backdrop="$emit('close')"
    :title="`${$t('jobs_history_title')} ${props.jobName}`"
    v-show="props.isOpen"
  >
    <div class="col-span-12 overflow-x-auto overflow-y-hidden">
      <ListBase
        class="min-w-[500px]"
        :header="[
          $t('jobs_history_headers_success'),
          $t('jobs_history_headers_start_date'),
          $t('jobs_history_headers_end_date'),
        ]"
        :positions="positions"
      >
        <ListItem v-for="(item, id) in props.history">
          <td class="translate-x-3 col-span-2" :class="[positions[0]]">
            <JobsSvgState :success="item['success']" />
          </td>
          <td :class="[positions[1]]">{{ item["start_date"] }}</td>
          <td :class="[positions[2]]">{{ item["end_date"] }}</td>
        </ListItem>
      </ListBase>
    </div>

    <div class="w-full mt-2">
      <div class="mt-2 w-full justify-end flex">
        <ButtonBase
          color="close"
          size="lg"
          @click="$emit('close')"
          type="button"
          class="text-xs"
          :aria-controls="`history-modal-${props.jobName}`"
          :aria-expanded="props.isOpen ? 'true' : 'false'"
        >
          {{ $t("action_close") }}
        </ButtonBase>
      </div>
    </div>
  </ModalBase>
</template>
