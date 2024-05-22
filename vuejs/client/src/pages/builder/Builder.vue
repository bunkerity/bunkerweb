<script setup>
import { reactive, onBeforeMount } from "vue";
import Builder from "@components/Builder.vue";

// Define reactive properties
const data = reactive({
  // Define properties here
  title: "No title",
});

// Retrieve default or flask data if available
onBeforeMount(() => {
  const dataEl = document.querySelector("[data-flask]");
  data.title =
    dataEl.getAttribute("data-flask") &&
    dataEl.getAttribute("data-flask") !== "{{ flask_data }}"
      ? dataEl.getAttribute("data-flask")
      : dataEl.getAttribute("data-default-value");
});

// Example of builder
const builder = [
  {
    // we are starting with the top level container name
    // this can be a "card", "modal", "table"... etc
    type: "card",
    containerColumns: { pc: 12, tablet: 12, mobile: 12 },
    // Each widget need a name (here type) and associated data
    // We need to send specific data for each widget type
    widgets: [
      {
        type: "TitleCard",
        data: { title: "My card title" },
      },
      {
        type: "Checkbox",
        data: {
          containerClass: "",
          columns: { pc: 6, tablet: 12, mobile: 12 },
          id: "test-check",
          value: "yes",
          label: "Checkbox",
          name: "checkbox",
          required: true,
          version: "v1.0.0",
          hideLabel: false,
          headerClass: "",
        },
      },
      {
        type: "Select",
        data: {
          containerClass: "",
          columns: { pc: 6, tablet: 12, mobile: 12 },
          id: "test-select",
          value: "yes",
          values: ["yes", "no"],
          name: "test-select",
          disabled: false,
          required: true,
          label: "Test select",
          tabId: "1",
        },
      },
    ],
  },
  {
    // we are starting with the top level container name
    // this can be a "card", "modal", "table"... etc
    type: "card",
    containerClass: "", // tailwind css grid class (items-start, ...)
    containerColumns: { pc: 12, tablet: 12, mobile: 12 },
    // container title
    title: "My awesome card",
    // Each widget need a name (here type) and associated data
    // We need to send specific data for each widget type
    widgets: [
      {
        type: "StatIcon",
        data: {
          iconName: "crown",
          iconColor: "yellow",
          iconClass: "col-span-12",
        },
      },
      {
        type: "StatTitle",
        data: {
          title: "stat title",
          titleClass: "col-span-12",
        },
      },
      {
        type: "StatValue",
        data: {
          value: "20",
          valueClass: "col-span-12",
        },
      },
      {
        type: "StatSubtitle",
        data: {
          subtitle: "some subtitle",
          subtitleClass: "col-span-12",
        },
      },
    ],
  },
];
</script>

<template>
  <div class="bg-secondary flex flex-col items-center justify-center h-full">
    <div style="width: 600px">
      <Builder :builder="builder" />
    </div>
  </div>
</template>
