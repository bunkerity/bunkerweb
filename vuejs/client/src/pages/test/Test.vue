<script setup>
import { reactive, onBeforeMount } from "vue";
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Select from "@components/Forms/Field/Select.vue";
import Input from "@components/Forms/Field/Input.vue";

// Define reactive properties
const data = reactive({
    // Define properties here
    title : 'No title'
})

// Retrieve default or flask data if available
onBeforeMount(() => {
  const dataEl = document.querySelector('[data-flask]');
  data.title = dataEl.getAttribute('data-flask') && dataEl.getAttribute('data-flask') !== "{{ flask_data }}" ? dataEl.getAttribute('data-flask') : dataEl.getAttribute('data-default-value');
})

const checkboxData = {
  id: 'test-checkbox',
  value: 'yes',
  name: 'test-checkbox',
  disabled: false,
  required: true,
  label: 'Test checkbox',
  tabId: '1',

}

const selectData = {
  id: 'test-select',
  value: 'yes',
  values: ['yes', 'no'],
  name: 'test-select',
  disabled: false,
  required: true,
  label: 'Test select',
  tabId: '1',
}

const inputData = {
  id: 'test-input',
  value: 'yes',
  type: "text",
  name: 'test-input',
  disabled: false,
  required: true,
  label: 'Test input',
  pattern : "(test)",
  tabId: '1',
}

</script>

<template>
    <div class="bg-secondary flex flex-col items-center justify-center h-full">
      <div style="width: 300px;">
        <Checkbox v-bind="checkboxData" />
        <Select v-bind="selectData" />
        <Input v-bind="inputData" />
      </div>
    </div>
</template>
