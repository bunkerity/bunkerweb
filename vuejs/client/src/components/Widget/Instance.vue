<script setup>
import { defineProps } from "vue";
import Container from "@components/Widget/Container.vue";
import TitleCardContent from "@components/Title/CardContent.vue";
import IconStatus from "@components/Icon/Status.vue";
import ContentDetailList from "@components/Content/DetailList.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";

/** 
  @name Widget/Instance.vue
  @description This component is an instance widget.
  This component is using the Container, TitleCardContent, IconStatus, ContentDetailList and ButtonGroup components.
  @example
  {
    id: "instance-1",
    title: "Instance 1",
    status: "success",
    details: [
      { key: "Version", value: "1.0.0" },
      { key: "Status", value: "Running" },
      { key: "Created", value: "2021-01-01" },
    ],
    buttons : [
      {
        id: "open-modal-btn",
        text: "Open modal",
        disabled: false,
        hideText: true,
        color: "green",
        size: "normal",
        iconName: "modal",
        iconColor: "white",
        eventAttr: {"store" : "modal", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},
      },
    ]
  }
  @param {string} id
  @param {string} title
  @param {string} status
  @param {array} details - List of details to display
  @param {array} buttons - List of buttons to display
*/

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  status: {
    type: String,
    required: true,
    default: "",
  },
  details: {
    type: Array,
    required: true,
    default: [],
  },
  buttons: {
    type: Array,
    required: true,
    default: [],
  },
});
</script>

<template>
  <Container :columns="{ pc: 12, tablet: 12, mobile: 12 }">
    <IconStatus :id="props.title" :status="props.status" />
    <TitleCardContent :title="props.title" />
    <ContentDetailList :details="props.details" />
    <ButtonGroup
      :id="props.id"
      :buttons="props.buttons"
      :groupClass="'justify-end align-center'"
    />
  </Container>
</template>
