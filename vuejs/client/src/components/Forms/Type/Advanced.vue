<script setup>
import { reactive, defineProps, onMounted, ref } from "vue";
import Container from "@components/Widget/Container.vue";
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Input from "@components/Forms/Field/Input.vue";
import Select from "@components/Forms/Field/Select.vue";
import Datepicker from "@components/Forms/Field/Datepicker.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";

/** 
  @name Forms/Type/Advanced.vue
  @description This component is used to create a complete advanced form with plugin selection.
  @example
  const data = [
    {
      name: "plugin name",
      type: "pro",
      is_activate: true,
      description: "plugin description",
      page: "/page",
      settings: [
        {
          columns: { pc: 6, tablet: 12, mobile: 12 },
          id: "test-check",
          value: "yes",
          label: "Checkbox",
          name: "checkbox",
          required: true,
          hideLabel: false,
          headerClass: "text-red-500",
          inpType: "checkbox",
        },
        {
          id: "test-input",
          value: "yes",
          type: "text",
          name: "test-input",
          disabled: false,
          required: true,
          label: "Test input",
          pattern: "(test)",
          inpType: "input",
        },
      ],
    },
  ];
  @param {object} forms - List of advanced forms that contains settings.
  @param {boolean} [isActive=true] - Check if the form is active, it will display the form if true
*/

const props = defineProps({
  // id && value && method
  forms: {
    type: Object,
    required: true,
    default: {},
  },
  isActive: {
    type: Boolean,
    required: false,
    default: true,
  },
});
</script>

<template>
  <Container
    v-if="props.isActive"
    :tag="'form'"
    method="POST"
    :containerClass="`col-span-12 w-full m-1 p-1`"
    :columns="props.columns"
  >
    <Container class="col-span-12 w-full" v-for="plugin in plugins">
      <Title type="card" :title="plugin.name" />
      <Subtitle type="card" :subtitle="plugin.description" />

      <Container class="grid grid-cols-12 w-full">
        <template v-for="(setting, index) in plugin.settings" :key="index">
          <Checkbox v-if="setting.inpType === 'checkbox'" v-bind="setting" />
          <Select v-if="setting.inpType === 'select'" v-bind="setting" />
          <Datepicker
            v-if="setting.inpType === 'datepicker'"
            v-bind="setting"
          />
          <Input v-if="setting.inpType === 'input'" v-bind="setting" />
        </template>
      </Container>
    </Container>
  </Container>
</template>
