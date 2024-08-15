<script setup>
import { defineProps, reactive, onMounted, watch } from "vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import Text from "@components/Widget/Text.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import { useDisplayStore } from "@store/global.js";

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
 * @param {String} [title=""] - Form title
 * @param {String} [subtitle=""] - Form subtitle
 * @param {Object} fields - List of Fields component to display
 * @param {Object} buttons - We need to send a regular ButtonGroup buttons prop
 * @param {String} [containerClass=""] - Container additional class
 * @param {String} [endpoint=""] - Form endpoint. Case none, will be ignored.
 * @param {String} [method="POST"] - Http method to be used on form submit.
 * @param {Array} [display=[]] - Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef.
 * @param {String} [maxWidthScreen="lg"] - Max screen width for the settings based on the breakpoint (xs, sm, md, lg, xl, 2xl)
 * @param {Object} [columns={ "pc": "12", "tablet": "12", "mobile": "12" }] - Columns object.
 */

const props = defineProps({
  // id && value && method
  title: {
    type: String,
    required: false,
    default: "",
  },
  subtitle: {
    type: String,
    required: false,
    default: "",
  },
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
  display: {
    type: Array,
    required: false,
    default: [],
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

const displayStore = useDisplayStore();

const data = reactive({
  base: props.fields,
  endpoint: props.endpoint,
  isRegErr: false,
  isReqErr: false,
  settingErr: "",
  pluginErr: "",
  isUpdateData: false,
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
  data.isDisplay = displayStore.isCurrentDisplay(
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

onMounted(() => {
  data.endpoint =
    window.location.origin + window.location.pathname + props.endpoint;
});
</script>

<template>
  <Container
    v-if="data.isDisplay"
    data-is="form-regular"
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
        <Title v-if="props.title" type="card" :title="props.title" />
        <Subtitle
          v-if="props.subtitle"
          type="card"
          :subtitle="props.subtitle"
        />

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
