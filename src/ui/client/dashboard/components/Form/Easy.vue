<script setup>
import {
  defineProps,
  reactive,
  onMounted,
  onUnmounted,
  computed,
  watch,
} from "vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Button from "@components/Widget/Button.vue";
import Text from "@components/Widget/Text.vue";
import GroupMultiple from "@components/Forms/Group/Multiple.vue";
import MessageUnmatch from "@components/Message/Unmatch.vue";
import { v4 as uuidv4 } from "uuid";
import { useCheckPluginsValidity } from "@utils/global.js";
import { useEasyForm } from "@store/form.js";

/**
 * @name Form/Easy.vue
 * @description This component is used to create a complete easy form with plugin selection.
 * @example
 * {
 *   template: [
 *         {
 *           columns: { pc: 6, tablet: 12, mobile: 12 },
 *           id: "test-check",
 *           value: "yes",
 *           label: "Checkbox",
 *           name: "checkbox",
 *           required: true,
 *           hideLabel: false,
 *           headerClass: "text-red-500",
 *           inpType: "checkbox",
 *         },
 *         {
 *           id: "test-input",
 *           value: "yes",
 *           type: "text",
 *           name: "test-input",
 *           disabled: false,
 *           required: true,
 *           label: "Test input",
 *           pattern: "(test)",
 *           inpType: "input",
 *         },
 *   ],
 * }
 * @param {Object} template - Template object with plugin and settings data.
 * @param {string} containerClass - Container
 * @param {string} [operation="edit"] - Operation type (edit, new, delete).
 * @param {string} [oldServerName=""] - Old server name. This is a server name before any changes.
 * @param {Object} columns - Columns object.
 */

const easyForm = useEasyForm();

const props = defineProps({
  // id && value && method
  template: {
    type: Object,
    required: true,
    default: {},
  },
  operation: {
    type: String,
    required: false,
    default: "edit",
  },
  oldServerName: {
    type: String,
    required: false,
    default: "",
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
  base: JSON.parse(JSON.stringify(props.template)),
  currStep: 0,
  totalSteps: computed(() => Object.keys(props.template).length),
  isFinalStep: computed(() => data.currStep === data.totalSteps - 1),
  isFirstStep: computed(() => data.currStep === 0),
  isRegErr: false,
  isReqErr: false,
  settingErr: "",
  stepErr: "",
});

watch(
  () => props.template,
  () => {
    setup();
  }
);

/**
 * @name setValidity
 * @description Check template settings and return if there is any error.
 * Error will disabled save button and display an error message.
 * @returns {void}
 */
function setValidity() {
  const [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id] =
    useCheckPluginsValidity(easyForm.templateUI, "easy");

  data.stepErr = id + 1;
  data.isRegErr = isRegErr;
  data.isReqErr = isReqErr;
  data.settingErr = `"${settingNameErr}"`;
}

/**
 * @name setup
 * @description Setup the needed data for the component to work properly.
 * @returns {void}
 */
function setup() {
  // Restart step one every time the component is mounted
  easyForm.setTemplate(props.template, true);
  easyForm.setOperation(props.operation);
  easyForm.setOldServerName(props.oldServerName);
  data.currStep = 0;
  setValidity();
}

/**
 * @name listenToValidate
 * @description Setup the needed data for the component to work properly.
 * @returns {void}
 */
function listenToValidate(e) {
  setTimeout(() => {
    if (!e.target.closest('[data-is="form"]')) return;
    setValidity();
  }, 50);
}

const buttonSave = {
  id: `easy-mode-${uuidv4()}`,
  text: "action_save",
  color: "success",
  size: "normal",
  type: "submit",
  containerClass: "flex justify-center",
};

const buttonPrev = {
  id: `easy-mode-${uuidv4()}`,
  text: "action_previous",
  color: "info",
  size: "normal",
};

const buttonNext = {
  id: `easy-mode-${uuidv4()}`,
  text: "action_next",
  color: "info",
  size: "normal",
};

onMounted(() => {
  setup();
  // I want updatInp to access event, data.base and the container attribute
  easyForm.useListenTempFields();
  window.addEventListener("input", listenToValidate);
});

onUnmounted(() => {
  easyForm.useUnlistenTempFields();
  window.removeEventListener("input", listenToValidate);
});
</script>

<template>
  <Container
    data-easy-form
    data-is="form"
    :tag="'form'"
    method="POST"
    :containerClass="`form-easy-container`"
    :columns="props.columns"
  >
    <Title type="card" :title="'dashboard_easy_mode'" />
    <Subtitle type="card" :subtitle="'dashboard_easy_mode_subtitle'" />
    <MessageUnmatch
      v-if="easyForm.templateUIFormat.length <= 0"
      :text="'services_no_easy_mode'"
    />

    <template v-if="easyForm.templateUIFormat.length > 0">
      <template v-for="(step, id) in easyForm.templateUIFormat">
        <Container
          data-is="content"
          data-easy-form-step
          v-if="data.currStep === id"
          class="form-easy-step-container"
        >
          <Title
            type="content"
            :title="
              $t('dashboard_easy_mode_title', {
                step: id + 1,
                total: data.totalSteps,
                name: step.title,
              })
            "
          />
          <Subtitle type="content" :subtitle="step.subtitle" />

          <Container class="layout-settings min-h-[300px]">
            <template v-for="plugin in step.plugins">
              <template
                v-for="(setting, name, index) in plugin.settings"
                :key="name"
              >
                <Fields :setting="setting" />
              </template>
              <GroupMultiple
                @delete="
                  (multName, groupName) =>
                    easyForm.delMultiple(plugin.id, multName, groupName)
                "
                @add="(multName) => easyForm.addMultiple(plugin.id, multName)"
                :multiples="plugin.multiples"
              />
            </template>
          </Container>
        </Container>
      </template>
      <div class="flex justify-center items-center">
        <Button
          @click="data.currStep = Math.max(data.currStep - 1, 0)"
          :disabled="data.isFirstStep"
          v-bind="buttonPrev"
          :containerClass="`mr-2`"
        />
        <Button
          :containerClass="`mr-2`"
          @click="data.currStep = Math.min(data.currStep + 1, data.totalSteps)"
          :disabled="data.isFinalStep"
          v-bind="buttonNext"
        />
        <Button
          :disabled="!data.isFinalStep || data.isRegErr || data.isReqErr"
          v-bind="buttonSave"
        />
      </div>
      <div class="flex justify-center items-center" data-is="form-error">
        <Text
          v-if="data.isRegErr || data.isReqErr"
          :text="
            data.isReqErr
              ? $t('dashboard_easy_required', {
                  step: data.stepErr,
                  setting: data.settingErr,
                })
              : $t('dashboard_easy_invalid', {
                  step: data.stepErr,
                  setting: data.settingErr,
                })
          "
        />
      </div>
    </template>
  </Container>
</template>
