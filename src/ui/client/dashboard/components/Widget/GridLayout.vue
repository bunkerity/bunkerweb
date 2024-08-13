<script setup>
import { computed, ref, onMounted, reactive, onBeforeMount, watch } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { useUUID } from "@utils/global.js";
import { useDisplayStore } from "@store/global.js";

/**
 *  @name Widget/GridLayout.vue
 *  @description This component is used for top level page layout.
 *  This will determine the position of layout components based on the grid system.
 *  We can create card, modal, table and others top level layout using this component.
 *  This component is mainly use as Grid parent component.
 *  @example
 *  {
 *    type: "card",
 *    title: "Test",
 *    columns: { pc: 12, tablet: 12, mobile: 12},
 *    gridLayoutClass: "items-start",
 *   display: ["main", 1],
 *  }
 *  @param {String} [type="card"] - Type of layout component, we can have "card"
 *  @param {String} [id=uuidv4()] - Id of the layout component, will be used to identify the component.
 *  @param {String} [title=""] - Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title.
 *  @param {String} [link=""] - Will transform the container tag from a div to an a tag with the link as href. Useful with card type.
 *  @param {Object} [columns={"pc": 12, "tablet": 12, "mobile": 12}] - Work with grid system { pc: 12, tablet: 12, mobile: 12}
 *  @param {String} [gridLayoutClass="items-start"] - Additional class
 *  @param {Array} [display=[]] - Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef.
 *  @param {String} [tabId=contentIndex] - Case the container is converted to an anchor with a link, we can define the tabId, by default it is the contentIndex
 * @param {string} [maxWidthScreen="2xl"] - Max screen width for the settings based on the breakpoint (xs, sm, md, lg, xl, 2xl, 3xl)
 */

const props = defineProps({
  type: {
    type: String,
    required: false,
    default: "card",
  },
  id: {
    type: String,
    required: false,
    default: "",
  },
  title: {
    type: String,
    required: false,
    default: "",
  },
  link: {
    type: String,
    required: false,
    default: "",
  },
  tabId: {
    type: String,
    required: false,
    default: contentIndex,
  },
  columns: {
    type: Object,
    required: false,
    default: {
      pc: 12,
      tablet: 12,
      mobile: 12,
    },
  },
  gridLayoutClass: {
    type: String,
    required: false,
    default: "items-start",
  },
  display: {
    type: Array,
    required: false,
    default: [],
  },
  maxWidthScreen: {
    type: String,
    required: false,
    default: "2xl",
  },
});

const displayStore = useDisplayStore();

const container = reactive({
  id: "",
  // Check if component display is related to the displayStore
  isDisplay: props.display.length
    ? displayStore.isCurrentDisplay(props.display[0], props.display[1])
    : true,
});

/**
 *  @name checkDisplay
 *  @description Check if the current display value is matching the display store value.
 *  @returns {Void}
 */
function checkDisplay() {
  if (!props.display.length) return;
  container.isDisplay = displayStore.isCurrentDisplay(
    props.display[0],
    props.display[1]
  );
}

// Case we have set a display group name and component id, the component id must match the current display id for the same group name to be displayed.
if (props.display.length) {
  watch(displayStore.display, (val) => {
    checkDisplay();
  });
}

const containerClass = computed(() => {
  if (props.type === "card") return "layout-card";
  if (props.type === "tabs") return "layout-tabs";
  return "";
});

const gridClass = computed(() => {
  return `w-full col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`;
});

const flowEl = ref();

onBeforeMount(() => {
  container.id = useUUID(props.id);
});

onMounted(() => {
  if (!props.link) return;
  flowEl.value.setAttribute("href", props.link);
  flowEl.value.setAttribute("rel", "noopener");
  flowEl.value.setAttribute("tabindex", props.tabId);

  if (!props.link.startsWith("http")) return;

  flowEl.value.setAttribute("target", "_blank");
});
</script>

<template>
  <component
    v-show="container.isDisplay"
    :aria-hidden="container.isDisplay ? 'false' : 'true'"
    ref="flowEl"
    :id="container.id"
    :is="props.link ? 'a' : 'div'"
    :data-is="`${props.type}`"
    :class="[
      containerClass,
      gridClass,
      props.gridLayoutClass,
      `max-w-screen-${props.maxWidthScreen}`,
    ]"
  >
    <slot></slot>
  </component>
  <!-- end card or elements on the document flow -->
</template>
