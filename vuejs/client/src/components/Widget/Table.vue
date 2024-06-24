<script setup>
import { reactive, computed, ref, onMounted, watch } from "vue";
import { v4 as uuidv4 } from "uuid";
import MessageUnmatch from "@components/Message/Unmatch.vue";
import Container from "@components/Widget/Container.vue";
import Text from "@components/Widget/Text.vue";
import Icons from "@components/Widget/Icons.vue";
import Fields from "@components/Form/Fields.vue";
import Button from "@components/Widget/Button.vue";
import Filter from "@components/Widget/Filter.vue";

/**
  @name Widget/Table.vue
  @description This component is used to create a table.
  You need to provide a title, a header, a list of positions, and a list of items.
  Items need to be an array of array with a cell being a regular widget. Not all widget are supported. Check this component import list to see which widget are supported.
  For example, Text, Icons, Icons, Buttons and Fields are supported.
  @example
  {
  "title": "Table title",
  "header": ["Header 1", "Header 2", "Header 3"],
  "minWidth": "base",
  "positions": [4,4,4],
  "items": [
            [
        {
          "type": "Text",
          "data": {
              "text": "whitelist-download"

            }
        },
        ...
      ],
      ...
    ],

  const  filters = [
  {
    filter: "default",
    filterName: "type",
    type: "select",
    value: "all",
    keys: ["type"],
    field: {
      id: uuidv4(),
      value: "all",
      // add 'all' as first value
      values: ["all"].concat(plugin_types),
      name: uuidv4(),
      onlyDown: true,
      label: "inp_select_plugin_type",
      containerClass: "setting",
      popovers: [
        {
          text: "inp_select_plugin_type_desc",
          iconName: "info",
        },
      ],
      columns: { pc: 3, tablet: 4, mobile: 12 },
    },
  },
  ...
  }

  @param {string} title - Determine the title of the table.
  @param {array} header - Determine the header of the table.
  @param {array} positions - Determine the position of each item in the table in a list of number based on 12 columns grid.
  @param {array} items - items to render in the table. This need to be an array (row) of array (cols) with a cell being a regular widget.
  @param {array} [filters=[]] - Determine the filters of the table.
  @param {string} [minWidth="base"] - Determine the minimum size of the table. Can be "base", "sm", "md", "lg", "xl".
  @param {string} [containerClass=""] - Container additional class.
  @param {string} [containerWrapClass=""] - Container wrap additional class.
  @param {string} [tableClass=""] - Table additional class.
*/

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  filters: {
    type: Array,
    required: false,
    default: [],
  },
  minWidth: {
    type: String,
    required: false,
    default: "base",
  },
  positions: {
    type: Array,
    required: true,
  },
  header: {
    type: Array,
    required: true,
  },
  items: {
    type: Array,
    required: true,
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  containerWrapClass: {
    type: String,
    required: false,
    default: "",
  },
  tableClass: {
    type: String,
    required: false,
    default: "",
  },
});

const tableBody = ref(null);
const tableHeader = ref(null);
const unmatchEl = ref(null);
const unmatchWidth = ref("");

const table = reactive({
  id: uuidv4(),
  overflow: "0px",
  length: computed(() => {
    return props.header.length;
  }),
  rowLength: computed(() => {
    return table.itemsFormat.length;
  }),
  title: computed(() => {
    return props.title ? props.title : "dashboard_table";
  }),
  // base items that never change
  itemsBase: JSON.parse(JSON.stringify(props.items)),
  // items that can be filtered
  itemsFormat: JSON.parse(JSON.stringify(props.items)),
});

const unmatch = {
  text: "dashboard_no_match",
  icons: {
    iconName: "search",
    color: "info",
  },
};

function setUnmatchWidth() {
  try {
    const value = tableBody.value.closest("[data-is='card']").clientWidth - 60;
    unmatchWidth.value = `${value}px`;
  } catch (e) {}
}

function getOverflow() {
  setTimeout(() => {
    const overflow =
      +tableBody.value.getBoundingClientRect().width -
      +tableBody.value.clientWidth;

    table.overflow = tableHeader.value.style.paddingRight = `${overflow}px`;
    if (overflow <= 0) {
      return tableHeader.value.removeAttribute("style");
    }
  }, 10);
}

// whatch itemsFormat changes
watch(
  () => table.itemsFormat,
  () => {
    getOverflow();
    setUnmatchWidth();
  }
);

onMounted(() => {
  getOverflow();
  setUnmatchWidth();
});
</script>

<template>
  <Container :containerClass="`${props.containerClass} table-container`">
    <Filter
      v-if="filters.length"
      @filter="(v) => (table.itemsFormat = v)"
      :data="table.itemsBase"
      :filters="filters"
    />
    <Container
      :containerClass="`${props.containerWrapClass} table-container-wrap`"
    >
      <span :id="`${table.id}-title`" class="sr-only"></span>
      <table
        data-is="table"
        :class="['table', props.minWidth, props.tableClass]"
        :aria-labelledby="`${table.id}-title`"
      >
        <thead
          ref="tableHeader"
          class="table-header"
          :style="{ paddingRight: table.overflow }"
        >
          <tr class="table-header-row">
            <th
              v-for="(head, id) in props.header"
              :class="['table-header-item', `col-span-${props.positions[id]}`]"
            >
              {{ $t(head, head) }}
            </th>
          </tr>
        </thead>

        <tbody
          v-show="table.itemsFormat.length"
          :aria-hidden="!table.itemsFormat.length ? 'true' : 'false'"
          data-table-body
          ref="tableBody"
          class="table-content"
        >
          <tr
            v-for="rowId in table.rowLength"
            :key="rowId - 1"
            class="table-content-item"
          >
            <template
              v-for="(col, id) in table.itemsFormat[rowId - 1]"
              :key="col"
            >
              <td
                :class="[
                  'table-content-item-wrap',
                  `col-span-${props.positions[id]}`,
                ]"
              >
                <Text v-if="col.type === 'Text'" v-bind="col.data" />
                <Icons v-if="col.type === 'Icons'" v-bind="col.data" />
                <Fields v-if="col.type === 'Fields'" v-bind="col.data" />
                <Button v-if="col.type === 'Button'" v-bind="col.data" />
              </td>
            </template>
          </tr>
        </tbody>
      </table>
      <div
        v-show="!table.itemsFormat.length"
        :aria-hidden="table.itemsFormat.length ? 'true' : 'false'"
        class="table-unmatch"
      >
        <MessageUnmatch
          v-if="!table.itemsFormat.length"
          :style="{ maxWidth: unmatchWidth }"
          ref="unmatchEl"
        />
      </div>
    </Container>
  </Container>
</template>
