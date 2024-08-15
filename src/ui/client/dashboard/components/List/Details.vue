<script setup>
import { defineProps, computed, reactive } from "vue";
import PopoverGroup from "@components/Widget/PopoverGroup.vue";
import Text from "@components/Widget/Text.vue";
import Filter from "@components/Widget/Filter.vue";
import Grid from "@components/Widget/Grid.vue";
import Unmatch from "@components/Message/Unmatch.vue";
/**
*  @name List/Details.vue
*  @description This component is a list of items separate on two columns : one for the title, and other for a list of popovers related to the plugin (type, link...)
*  @example
  {
  details : [{
    text: "name",
    disabled : false,
    attrs: {
      id: "id",
      value: "value",
    },
    popovers: [
      {
        text: "This is a popover text",
        iconName: "info",
      },
      {
        text: "This is a popover text",
        iconName: "info",
      },
    ],
}]
*  @param {string} details  - List of details item that contains a text, disabled state, attrs and list of popovers. We can also add a disabled key to disable the item.
*  @param {array} [filters=[]] - List of filters to apply on the list of items.
*  @param {columns} [columns={"pc": "4", "tablet": "6", "mobile": "12"}] - Determine the position of the items in the grid system.
*/

const props = defineProps({
  details: {
    type: Array,
    required: true,
  },
  filters: {
    type: Array,
    required: false,
    default: [],
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: { pc: 4, tablet: 6, mobile: 12 },
  },
});

const data = reactive({
  base: JSON.parse(JSON.stringify(props.details)),
  format: JSON.parse(JSON.stringify(props.details)),
  upIndex: "",
  pendingIndex: [],
});

const gridClass = computed(() => {
  return `col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`;
});

/**
 *  @name indexUp
 *  @description   When we focus or pointerover an item, we will add a higher z-index than others items in order to avoid to crop popovers.
 *  In case we leave the item, for few moments the item will get an higher z-index than this in order to get a smooth transition.
 *  @param {String|Number} id - The id of the item.
 *  @returns {Void}
 */
function indexUp(id) {
  data.upIndex = id;
}

/**
 *  @name indexPending
 *  @description  This will add a higher z-index for 100ms when cursor is out of the item in order to avoid to crop popovers.
 *  @param {String|Number} id - The id of the item.
 *  @returns {Void}
 */
function indexPending(id) {
  data.pendingIndex.push(id);
  // Remove id from pendingIndex after a moment
  setTimeout(() => {
    data.pendingIndex = data.pendingIndex.filter((index) => index !== id);
  }, 100);
}
</script>

<template>
  <Grid>
    <Filter
      v-if="props.filters.length"
      @filter="(v) => (data.format = v)"
      :data="data.base"
      :filters="props.filters"
    />
    <MessageUnmatch v-if="!data.format.length" />
    <ul
      data-is="list-details"
      v-if="data.format.length"
      :class="['list-details-container']"
    >
      <li
        v-for="(item, id) in data.format"
        :class="[
          'list-details-item',
          gridClass,
          item.disabled ? 'disabled' : 'enabled',
          data.upIndex === id
            ? 'up'
            : data.pendingIndex.includes(id)
            ? 'pending'
            : '',
        ]"
        v-bind="item.attrs || {}"
        @focusin="indexUp(id)"
        @pointerover="indexUp(id)"
        @focusout="indexPending(id)"
        @pointerleave="indexPending(id)"
      >
        <div class="list-details-item-wrap">
          <Text :tag="'p'" :text="item.text" />
          <div>
            <PopoverGroup :popovers="item.popovers" />
          </div>
        </div>
      </li>
    </ul>
  </Grid>
</template>
