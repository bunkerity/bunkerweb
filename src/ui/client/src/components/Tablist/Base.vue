<script setup>
import { reactive } from "vue";

const props = defineProps({
  current: {
    type: String,
    required: true,
  },
  items: {
    type: Array,
    required: true,
    // [{text: "Ban list", tag: "list"}]
  },
});

const tabs = reactive({
  current: props.current,
  items: props.items,
  inactiveTabClass:
    "inline-flex items-center justify-center p-4 hover:border-b-2 border-transparent rounded-t-lg hover:text-gray-700 hover:border-gray-700 border-gray-600 dark:border-gray-300 dark:hover:text-gray-300 text-gray-600 dark:text-gray-500 group",
  activeTabClass:
    "bg-primary/10 dark:bg-gray-100/80 inline-flex items-center justify-center p-4 text-primary border-b-2 border-primary rounded-t-lg active dark:text-primary dark:border-primary group",
  inactiveSvgClass:
    "mr-2.5 text-gray-600 group-hover:text-gray-700 dark:text-gray-500 dark:group-hover:text-gray-300 text-gray-600",
  activeSvgClass: "mr-2.5 text-primary dark:text-primary",
});
const emits = defineEmits(["tab"]);
</script>

<template>
  <div
    class="my-2 col-span-12 border-b border-gray-200 dark:border-gray-700 w-full"
  >
    <ul
      role="tablist"
      class="flex flex-wrap -mb-px text-sm font-medium text-center text-gray-500 dark:text-gray-400"
    >
      <li
        v-for="(item, id) in tabs.items"
        role="tab"
        :tabindex="id"
        :aria-selected="tabs.current === item.tag ? 'true' : 'false'"
        class="mr-2 uppercase font-bold"
      >
        <button
          class="min-w-[60px]"
          @click="
            () => {
              tabs.current = item.tag;
              $emit('tab', item.tag);
            }
          "
          :class="[
            tabs.current === item.tag
              ? tabs.activeTabClass
              : tabs.inactiveTabClass,
          ]"
          :aria-current="tabs.current === item.tag ? 'page' : false"
        >
          {{ item.text }}
        </button>
      </li>
    </ul>
  </div>
</template>
