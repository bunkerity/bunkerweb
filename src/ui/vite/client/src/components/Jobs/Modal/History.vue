<script setup>
import { defineProps, defineEmits } from "vue";
import ButtonBase from "@components/Button/Base.vue";
import ModalBase from "@components/Modal/Base.vue";
import JobsSvgState from "@components/Jobs/Svg/State.vue";
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

const header = ["success", "start date", "end date"];

const emits = defineEmits(["close"]);
</script>
<template>
  <ModalBase :title="`history ${props.jobName}`" v-if="props.isOpen">
    <div class="w-full">
      <section class="w-full">
        <div
          class="grid grid-cols-12 dark:text-gray-300 text-sm font-bold m-0 border-b border-gray-400"
        >
          <label
            class="dark:text-gray-300 pb-1 text-sm font-bold m-0 border-gray-400"
            v-for="(item, id) in header"
            :class="[positions[id]]"
          >
            {{ item }}
          </label>
        </div>
        <ul class="w-full overflow-auto max-h-[300px]">
          <li
            v-for="(item, id) in props.history"
            class="items-center grid grid-cols-12 border-b border-gray-300 py-2.5"
          >
            <div
              class="break-words items-center col-span-12 grid grid-cols-12 text-sm dark:text-gray-400"
            >
              <div class="translate-x-3 col-span-2" :class="[positions[0]]">
                <JobsSvgState :success="item['success']" />
              </div>
              <span :class="[positions[1]]">{{ item["start_date"] }}</span>
              <span :class="[positions[2]]">{{ item["end_date"] }}</span>
            </div>
          </li>
        </ul>
      </section>

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
      </div>
    </div>
  </ModalBase>
</template>
