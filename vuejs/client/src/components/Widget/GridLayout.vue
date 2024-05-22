<script setup>
import { computed, ref, onMounted } from "vue";

/** 
  @name Widget/GridLayout.vue
  @description This component is used for top level page layout.
  This will determine the position of layout components based on the grid system.
  We can create card, modal, table and others top level layout using this component.
  This component is mainly use as Grid parent component.
  @example
  {
    type: "card",
    title: "Test",
    columns: { pc: 12, tablet: 12, mobile: 12},
    gridLayoutClass: "items-start"
  }
  @param {string} [type="card"] - Type of layout component, we can have : card, table, modal and others
  @param {string} [title=""] - Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title.
  @param {string} [link=""] - Will transform the container tag from a div to an a tag with the link as href. Useful with card type.
  @param {object} [columns={"pc": 12, "tablet": 12, "mobile": 12}] - Work with grid system { pc: 12, tablet: 12, mobile: 12}
  @param {string} [gridLayoutClass="items-start"] - Additional class
*/

const props = defineProps({
  type: {
    type: String,
    required: false,
    default: "card",
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
});

const containerClass = computed(() => {
  if (props.type === "card") return "card";
  return "";
});

const gridClass = computed(() => {
  return `break-words grid grid-cols-12 w-full col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`;
});

const titleClass = computed(() => {
  if (props.type === "card") return "text-2xl font-bold mb-2";
  return "";
});

const gridLayoutEl = ref();

onMounted(() => {
  if (props.link) {
    gridLayoutEl.value.setAttribute("href", props.link);
    gridLayoutEl.value.setAttribute("rel", "noopener");
  }

  if (props.link && props.link.startsWith("http")) {
    gridLayoutEl.value.setAttribute("target", "_blank");
  }
});
</script>

<template>
  <component
    ref="gridLayoutEl"
    :is="props.link ? 'a' : 'div'"
    data-grid-layout
    :class="[containerClass, gridClass, props.gridLayoutClass, 'p-4']"
  >
    <h1 v-if="props.title" :class="[titleClass, 'col-span-12']">
      {{ $t(props.title, props.title) }}
    </h1>
    <slot></slot>
  </component>
</template>
