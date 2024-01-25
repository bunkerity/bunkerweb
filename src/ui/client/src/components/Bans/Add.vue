<script setup>
import ListBase from "@components/List/Base.vue";
import ListItem from "@components/List/Item.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsDatepicker from "@components/Settings/Datepicker.vue";
import SettingsUploadSvgWarning from "@components/Settings/Upload/Svg/Warning.vue";
import ButtonBase from "@components/Button/Base.vue";
import { fetchAPI } from "@utils/api.js";
import { useFeedbackStore } from "@store/global.js";
import { computed, reactive } from "vue";

const feedbackStore = useFeedbackStore();
const emits = defineEmits(["addBans"]);

const bans = reactive({
  count: 0,
  items: [],
  isInvalidAdd: computed(() => {
    // Check if some invalid value
    let isInvalid = false;
    for (let i = 0; i < bans.items.length; i++) {
      const item = bans.items[i];
      if (!item.end_date || !item.reason || !item.ip) isInvalid = true;
      if (isInvalid) break;
    }
    return isInvalid;
  }),
});

function addItem() {
  bans.items.push({
    id: bans.count,
    ip: "",
    reason: "Manual",
    start_date: Date.parse(new Date()),
    end_date: "",
  });
  bans.count++;
}

function deleteItem(itemId) {
  let bansId;
  bans.items.forEach((item, id) => {
    if (item.id === itemId) bansId = id;
  });
  bans.items.splice(bansId, 1);
}

function deleteAllItems() {
  bans.items = [];
}

const addPositions = [
  "col-span-3",
  "col-span-3",
  "col-span-3",
  "col-span-2",
  "col-span-1",
];

const addBans = reactive({
  isErr: false,
  isPend: false,
  data: [],
});

function getValidBans() {
  const validBans = [];
  bans.items.forEach((item) => {
    if (!item.ip || !item.reason || !item.start_date || !item.end_date) return;
    validBans.push(item);
  });
  return validBans;
}

async function addBansFromList() {
  await fetchAPI(
    `/api/instances/ban?method=ui`,
    "POST",
    getValidBans(),
    addBans,
    feedbackStore.addFeedback,
  ).then((res) => {
    // Case succeed, delete items from UI
    // And emit add event to refetch ban list
    if (res.type === "success") {
      deleteAllItems();
      emits("addBans");
      return;
    }
  });
}
</script>

<template>
  <div class="col-span-12 grid grid-cols-12">
    <div
      class="col-span-12 flex flex-col sm:flex-row justify-left items-center mt-2 mb-6 mx-2"
    >
      <ButtonBase
        @click="addItem()"
        color="valid"
        size="normal"
        class="text-sm mb-2 sm:mb-0"
      >
        <svg
          aria-hidden="true"
          role="img"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.5"
          stroke="currentColor"
          class="w-6 h-6 -translate-y-[1px]"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span class="ml-1 -translate-y-1">
          {{ $t("bans_add") }}
        </span>
      </ButtonBase>
      <ButtonBase
        :disabled="bans.items.length <= 0 ? true : false"
        @click="deleteAllItems()"
        color="delete"
        size="normal"
        class="text-sm ml-4"
      >
        <svg
          aria-hidden="true"
          role="img"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.5"
          stroke="currentColor"
          class="w-5.5 h-5.5 -translate-y-[1px]"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
          />
        </svg>
        <span class="ml-1 -translate-y-1">
          {{ $t("action_delete_all") }}
        </span>
      </ButtonBase>
    </div>
    <div class="overflow-x-auto col-span-12 grid grid-cols-12">
      <ListBase
        v-if="bans.items.length > 0"
        class="min-w-[1100px] h-full col-span-12"
        :header="[
          $t('bans_add_header_ip'),
          $t('bans_add_header_ban_start'),
          $t('bans_add_header_ban_end'),
          $t('bans_add_header_reason'),
          $t('action_delete'),
        ]"
        :positions="addPositions"
        :summary="$t('bans_add_table_summary')"
      >
        <ListItem
          v-for="(item, id) in bans.items"
          :key="id"
          :class="[id === bans.items.length - 1 ? '' : 'border-b', 'py-1.5']"
        >
          <td :class="[addPositions[0], 'mr-2']">
            <SettingsLayout
              :showLabel="false"
              :label="$t('bans_add_header_ip')"
              :name="`add-ip-${id}`"
            >
              <SettingsInput
                @inp="(v) => (item.ip = v)"
                :settings="{
                  id: `add-ip-${id}`,
                  type: 'text',
                  value: '',
                  placeholder: '127.0.0.1',
                }"
                :inpClass="item.ip ? '' : 'invalid'"
              />
            </SettingsLayout>
          </td>

          <td :class="[addPositions[1], 'mr-2']">
            <SettingsLayout
              :showLabel="false"
              :label="$t('bans_add_header_ban_start')"
              :name="`add-ban-date-deb-${id}`"
            >
              <SettingsDatepicker
                @inp="(v) => (item.ip = v)"
                :settings="{
                  id: `add-ban-date-deb-${id}`,
                  disabled: true,
                }"
                :defaultDate="new Date()"
                :noPickBeforeStamp="Date.parse(new Date())"
                :noPickAfterStamp="Date.parse(new Date())"
              />
            </SettingsLayout>
          </td>

          <td :class="[addPositions[2], 'mr-2']">
            <SettingsLayout
              :showLabel="false"
              :label="$t('bans_add_header_ban_end')"
              :name="`add-ban-date-end-${id}`"
            >
              <SettingsDatepicker
                :settings="{
                  id: `add-ban-date-end-${id}`,
                }"
                @inp="(v) => (item.end_date = v.timestamp)"
                :inpClass="item.end_date ? '' : 'invalid'"
                :noPickBeforeStamp="Date.parse(new Date())"
              />
            </SettingsLayout>
          </td>

          <td :class="[addPositions[3], 'mr-2']">
            <SettingsLayout
              :showLabel="false"
              :label="$t('bans_add_header_reason')"
              :name="`add-reason-${id}`"
            >
              <SettingsInput
                @inp="(v) => (item.reason = v)"
                :settings="{
                  id: `add-reason-${id}`,
                  type: 'text',
                  value: item.reason,
                  placeholder: 'Manual',
                }"
                :inpClass="item.reason ? '' : 'invalid'"
              />
            </SettingsLayout>
          </td>

          <td
            :class="[addPositions[4]]"
            class="w-full flex justify-center items-center"
          >
            <ButtonBase
              :aria-describedby="`remove-ban-field-${id}`"
              @click="deleteItem(item.id)"
              color="delete"
              size="normal"
              class="text-sm mx-4 py-1.5"
            >
              <span :id="`remove-ban-field-${id}`" class="sr-only">
                {{ $t("bans_add_remove_ban_desc") }}
              </span>
              <svg
                role="img"
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke-width="1.5"
                stroke="currentColor"
                class="w-6 h-6"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                />
              </svg>
            </ButtonBase>
          </td>
        </ListItem>
      </ListBase>
    </div>

    <div
      v-if="bans.items.length > 0"
      class="col-span-12 flex flex-col items-center justify-center mt-6"
    >
      <ButtonBase
        type="submit"
        @click.prevent="addBansFromList()"
        :disabled="bans.isInvalidAdd || bans.isPend"
        :isLoading="bans.isPend"
        color="valid"
        size="normal"
        class="text-sm mb-2 sm:mb-0 w-fit"
      >
        {{ $t("action_save") }}
      </ButtonBase>
      <hr class="line-separator z-10 w-1/2" />
      <p class="dark:text-gray-500 text-xs text-center mt-1 mb-2">
        <span class="mx-0.5">
          <SettingsUploadSvgWarning class="scale-90" />
        </span>
        {{ $t("bans_add_save_bans_warning") }}
      </p>
    </div>
  </div>
</template>
