<script setup>
import Flex from "@components/Widget/Flex.vue";
import PopoverGroup from "@components/Widget/PopoverGroup.vue";
import Text from "@components/Widget/Text.vue";

/** 
  @name List/Popovers.vue
  @description This component is a list of items separate on two columns : one for the title, and other for a list of popovers related to the plugin (type, link...)
  @example
  {
  details : [{
    title: "name",
    disabled : false,
    popovers: [
      {
        text: "This is a popover text",
        iconName: "info",
        iconColor: "info",
      },
      {
        text: "This is a popover text",
        iconName: "info",
        iconColor: "info",
      },
    ],
}]
  @param {string}  details  - List of details item that contains a title and a list of popovers. We can also add a disabled key to disable the item.
  @param {columns} [columns={pc: 4, tablet: 6, mobile: 12}] - Determine the position of the items in the grid system.
*/

const props = defineProps({
  details: {
    type: Array,
    required: true,
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: { pc: 4, tablet: 6, mobile: 12 },
  },
});

const gridClass = computed(() => {
  return `col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`;
});
</script>

<template>
  <ul v-if="props.details" :class="['list-details-container']">
    <li
      v-for="item in props.details"
      :class="[
        'list-details-item',
        gridClass,
        item.disabled ? 'disabled' : 'enabled',
      ]"
    >
      <Flex :flexClass="'justify-between items-center'">
        <Text :tag="'p'" :text="props.name" />
        <div>
          <PopoverGroup :popovers="props.popovers" />
        </div>
      </Flex>
    </li>
  </ul>
</template>
