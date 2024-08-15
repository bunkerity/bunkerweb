<script setup>
import { defineProps, reactive, onMounted } from "vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import Text from "@components/Widget/Text.vue";

/**
 *  @name Form/Regular.vue
 *  @description This component is used to create a basic form with fields.
 *  @example
 * fields : [
 *        {
 *          columns: { pc: 6, tablet: 12, mobile: 12 },
 *          id: "test-check",
 *          value: "yes",
 *          label: "Checkbox",
 *          name: "checkbox",
 *          required: true,
 *          hideLabel: false,
 *          headerClass: "text-red-500",
 *          inpType: "checkbox",
 *        },
 *        {
 *          id: "test-input",
 *          value: "yes",
 *          type: "text",
 *          name: "test-input",
 *          disabled: false,
 *          required: true,
 *          label: "Test input",
 *          pattern: "(test)",
 *          inpType: "input",
 *        },
 *      ],
 * @param {Object} fields - List of Fields component to display
 * @param {Object} buttons - We need to send a regular ButtonGroup buttons prop
 * @param {String} [containerClass=""] - Container additional class
 * @param {String} [endpoint=""] - Form endpoint. Case none, will be ignored.
 * @param {String} [method="POST"] - Http method to be used on form submit.
 * @param {String} [maxWidthScreen="lg"] - Max screen width for the settings based on the breakpoint (xs, sm, md, lg, xl, 2xl)
 * @param {Object} [columns={ "pc": "12", "tablet": "12", "mobile": "12" }] - Columns object.
 */

const props = defineProps({
  // id && value && method
  fields: {
    type: Array,
    required: true,
    default: [],
  },
  buttons: {
    type: Array,
    required: false,
    default: {},
  },
  maxWidthScreen: {
    type: String,
    required: false,
    default: "lg",
  },
  endpoint: {
    type: String,
    required: false,
    default: "",
  },
  method: {
    type: String,
    required: false,
    default: "POST",
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  columns: {
    type: Object,
    required: false,
    default: { pc: 12, tablet: 12, mobile: 12 },
  },
});

const data = reactive({
  base: props.fields,
  endpoint: props.endpoint,
  isRegErr: false,
  isReqErr: false,
  settingErr: "",
  pluginErr: "",
  isUpdateData: false,
});

onMounted(() => {
  data.endpoint =
    window.location.origin + window.location.pathname + props.endpoint;
});
</script>

<template>
  <Container
    data-is="form"
    :tag="'form'"
    :method="props.method"
    :action="data.endpoint"
    :columns="props.columns"
    :containerClass="`form-regular-container`"
  >
    <div class="form-regular-wrap">
      <div
        :class="[
          'layout-settings-regular',
          `max-w-screen-${props.maxWidthScreen}`,
        ]"
      >
        <template v-for="(field, key) in props.fields">
          <Fields :setting="field.setting" />
        </template>
      </div>

      <ButtonGroup :buttons="props.buttons" />
      <div
        v-if="data.isRegErr || data.isReqErr"
        class="flex justify-center items-center"
        data-is="form-error"
      >
        <Text
          :text="
            data.isReqErr
              ? $t('dashboard_regular_required', {
                  setting: data.settingErr,
                })
              : $t('dashboard_regular_invalid', {
                  setting: data.settingErr,
                })
          "
        />
      </div>
    </div>
  </Container>
</template>
