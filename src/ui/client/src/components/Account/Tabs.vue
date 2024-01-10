<script setup>
import { reactive } from "vue";

const tabs = reactive({
  current: "username",
  items: ["username", "password", "totp"],
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
        <a
          @click="
            () => {
              tabs.current = item;
              $emit('tab', item);
            }
          "
          href="#"
          :class="[
            tabs.current === item ? tabs.activeTabClass : tabs.inactiveTabClass,
          ]"
          :aria-current="tabs.current === item ? 'page' : false"
        >
          <svg
            v-if="item === 'username'"
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
              d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
            />
          </svg>
          <svg
            v-if="item === 'password'"
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
              d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"
            />
          </svg>
          <svg
            v-if="item === 'totp'"
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
              d="M10.5 1.5H8.25A2.25 2.25 0 0 0 6 3.75v16.5a2.25 2.25 0 0 0 2.25 2.25h7.5A2.25 2.25 0 0 0 18 20.25V3.75a2.25 2.25 0 0 0-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3"
            />
          </svg>

          {{ $t(`account_tabs_${item}`) }}
        </a>
      </li>
    </ul>
  </div>
</template>
