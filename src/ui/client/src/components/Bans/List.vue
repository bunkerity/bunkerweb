<script setup>
import ListBase from "@components/List/Base.vue";
import ListItem from "@components/List/Item.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsCheckbox from "@components/Settings/Checkbox.vue";
import SettingsDatepicker from "@components/Settings/Datepicker.vue";
import ButtonBase from "@components/Button/Base.vue";
import { useSelectIPStore } from "@store/bans.js";
import { reactive } from "vue";
import { useFeedbackStore } from "@store/global.js";
import { fetchAPI } from "@utils/api.js";

const feedbackStore = useFeedbackStore();
const selectIPStore = useSelectIPStore();
const emits = defineEmits(["unban"]);

const props = defineProps({
  items: {
    type: Array,
    default: [],
  },
});

const listPositions = [
  "col-span-1",
  "col-span-2",
  "col-span-2",
  "col-span-2",
  "col-span-2",
  "col-span-3",
];

const listHeader = [
  "Check",
  "IP number",
  "Reason",
  "Ban start",
  "Ban End",
  "Remain",
];

function getRemain(ms) {
  let seconds = Math.floor(ms / 1000);
  let minutes = Math.floor(seconds / 60);
  let hours = Math.floor(minutes / 60);
  let days = Math.floor(hours / 24);
  let months = Math.floor(days / 30);
  let years = Math.floor(days / 365);
  seconds %= 60;
  minutes %= 60;
  hours %= 24;
  days %= 30;
  months %= 12;
  return `${years}y ${months}m ${days}d ${hours}h ${minutes}min ${seconds}s`;
}

function updateCheck(v, ip) {
  v === "no" ? selectIPStore.deleteIP(ip) : selectIPStore.addIP(ip);
}

const list = reactive({
  checkAll: false,
});

function toggleAllCheck() {
  list.checkAll = list.checkAll ? false : true;
  const banItemsChekbox = document.querySelectorAll(
    '#banlist-container input[type="checkbox"]',
  );
  banItemsChekbox.forEach((item) => {
    // Check current state to update
    if (item.value === "no" && list.checkAll) return item.click();
    if (item.value === "yes" && !list.checkAll) return item.click();
  });
}

const delBans = reactive({
  isErr: false,
  isPend: false,
  data: [],
});

async function sendUnban() {
  const unbanList = Array.from(selectIPStore.data);
  console.log(unbanList);
  await fetchAPI(
    `/api/instances/ban?method=ui`,
    "DELETE",
    unbanList,
    delBans,
    feedbackStore.addFeedback,
  ).then((res) => {
    if (res.type === "success") {
      // Case succeed, delete items from UI
      // And emit add event to refetch ban list
      list.checkAll = false;
      emits("unban");
      return;
    }
  });
}
</script>

<template>
  <div class="col-span-12 grid grid-cols-12">
    <div
      v-if="props.items.length === 0"
      class="col-span-12 flex flex-col justify-center items-center mt-2 mb-6 mx-2"
    >
      <p class="ml-1 mb-0 text-red-500 font-semibold">
        {{ $t("bans.list.no_bans") }}
      </p>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.5"
        stroke="currentColor"
        class="w-6 h-6 text-red-500"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    </div>
    <div
      v-if="props.items.length > 0"
      class="col-span-12 flex flex-col sm:flex-row justify-left items-center mt-2 mb-6 mx-2"
    >
      <ButtonBase
        @click="toggleAllCheck()"
        color="info"
        size="normal"
        class="text-sm mb-2 sm:mb-0"
      >
        <svg
          class="w-6 h-6 -translate-y-[1px]"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.5"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span class="ml-1.5">{{
          list.checkAll
            ? $t("bans.list.unselect_all")
            : $t("bans.list.select_all")
        }}</span>
      </ButtonBase>
    </div>
    <div
      v-if="props.items.length > 0"
      class="overflow-x-auto col-span-12 grid grid-cols-12"
    >
      <ListBase
        class="min-w-[1100px] h-full col-span-12"
        :header="listHeader"
        :positions="listPositions"
      >
        <div>
          <div id="banlist-container">
            <ListItem
              v-for="(item, id) in props.items"
              :class="[
                id === props.items.length - 1 ? '' : 'border-b',
                item.isMatchFilter ? '' : 'hidden',
                'py-1.5',
              ]"
            >
              <div class="list-content-item-wrap">
                <div :class="[listPositions[0], 'ml-2 mb-2 mr-2']">
                  <SettingsLayout class="" label="" :name="`check-${id}`">
                    <SettingsCheckbox
                      :aria-description="
                        $t('bans.list.select.aria_description')
                      "
                      @inp="(v) => updateCheck(v, item.ip)"
                      :settings="{
                        id: `check-${id}`,
                        value: 'no',
                      }"
                    />
                  </SettingsLayout>
                </div>
                <div :class="[listPositions[1], 'mr-2']">
                  <SettingsLayout label="" :name="`ip-${id}`">
                    <SettingsInput
                      :settings="{
                        id: `ip-${id}`,
                        type: 'text',
                        value: item.ip,
                        placeholder: '127.0.0.1',
                        disabled: true,
                      }"
                    />
                  </SettingsLayout>
                </div>
                <div :class="[listPositions[2], 'mr-2']">
                  <SettingsLayout label="" :name="`ip-reason-${id}`">
                    <SettingsInput
                      :settings="{
                        id: `ip-reason-${id}`,
                        type: 'text',
                        value: item.reason,
                        placeholder: '127.0.0.1',
                        disabled: true,
                      }"
                    />
                  </SettingsLayout>
                </div>
                <div :class="[listPositions[3], 'mr-2']">
                  <SettingsLayout label="" :name="`ban-deb-${id}`">
                    <SettingsDatepicker
                      :settings="{
                        id: `ban-deb-${id}`,
                        disabled: true,
                      }"
                      :defaultDate="new Date(+`${item.date}000`)"
                    />
                  </SettingsLayout>
                </div>
                <div :class="[listPositions[4], 'mr-2']">
                  <SettingsLayout label="" :name="`ban-end-${id}`">
                    <SettingsDatepicker
                      :settings="{
                        id: `ban-end-${id}`,
                        disabled: true,
                      }"
                      :defaultDate="Date.now() + `${item.exp}000`"
                    />
                  </SettingsLayout>
                </div>
                <div :class="[listPositions[5], 'ml-4']">
                  <p class="text-sm mb-0">
                    {{ getRemain(+`${item.exp}000`) }}
                  </p>
                </div>
              </div>
            </ListItem>
          </div>
        </div>
      </ListBase>
    </div>

    <div
      v-if="props.items.length > 0"
      class="col-span-12 flex justify-center mt-4"
    >
      <ButtonBase
        @click="sendUnban()"
        :aria-description="$t('bans.list.unban.aria_description')"
        color="delete"
        size="normal"
        class="text-sm ml-4"
        :disabled="selectIPStore.data.size > 0 ? false : true"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.5"
          stroke="currentColor"
          class="w-5.5 h-5.5 -translate-y-[2px]"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
          />
        </svg>
        <span class="ml-1.5">{{ $t("bans.list.unban.label") }}</span>
      </ButtonBase>
    </div>
  </div>
</template>
