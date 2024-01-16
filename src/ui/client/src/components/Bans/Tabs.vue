<script setup>
import { reactive } from "vue";

const tabs = reactive({
  current: "list",
  items: ["list", "add"],
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
  <div class="my-2 col-span-12 border-b border-gray-200 dark:border-gray-700">
    <ul
      role="tablist"
      class="flex flex-wrap -mb-px text-sm font-medium text-center text-gray-500 dark:text-gray-400"
    >
      <li
        v-for="(item, id) in tabs.items"
        role="tab"
        :tabindex="id"
        :aria-selected="tabs.current === item ? 'true' : 'false'"
        class="mr-2 uppercase font-bold"
      >
        <button
          @click="
            () => {
              tabs.current = item;
              $emit('tab', item);
            }
          "
          :class="[
            tabs.current === item ? tabs.activeTabClass : tabs.inactiveTabClass,
          ]"
          :aria-current="tabs.current === item ? 'page' : false"
        >
          <svg
            aria-hidden="true"
            role="img"
            v-if="item === 'list'"
            :class="[
              tabs.current === item
                ? tabs.activeSvgClass
                : tabs.inactiveSvgClass,
              'w-5 h-5',
            ]"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"
            />
          </svg>
          <svg
            role="img"
            aria-hidden="true"
            v-if="item === 'add'"
            :class="[
              tabs.current === item
                ? tabs.activeSvgClass
                : tabs.inactiveSvgClass,
              'h-5.5 w-5.5',
            ]"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          {{ $t(`bans_tabs_${item}`) }}
        </button>
      </li>
    </ul>
  </div>
</template>
