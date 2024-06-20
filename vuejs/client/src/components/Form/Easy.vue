<script setup>
import { defineProps, reactive, onMounted, onUnmounted, computed } from "vue";
import Container from "@components/Widget/Container.vue";
import Fields from "@components/Form/Fields.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Flex from "@components/Widget/Flex.vue";
import Button from "@components/Widget/Button.vue";
import Text from "@components/Widget/Text.vue";
import { v4 as uuidv4 } from "uuid";
import {
  useCheckPluginsValidity,
  useUpdateTempSettings,
  useListenTemp,
  useUnlistenTemp,
} from "@utils/form.js";

/**
  @name Form/Easy.vue
  @description This component is used to create a complete easy form with plugin selection.
  @example
  template: [
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
  @param {object} template - Template object with plugin and settings data.
  @param {string} containerClass - Container
  @param {object} columns - Columns object.
*/

const props = defineProps({
  // id && value && method
  template: {
    type: Object,
    required: true,
    default: {},
  },

  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  columns: {
    type: Object,
    required: false,
    default: {},
  },
});

const data = reactive({
  base: JSON.parse(JSON.stringify(props.template)),
  currStep: 0,
  totalSteps: Object.keys(props.template).length,
  isFinalStep: computed(() => data.currStep === data.totalSteps - 1),
  isFirstStep: computed(() => data.currStep === 0),
  isRegErr: false,
  isReqErr: false,
  settingErr: "",
  stepErr: "",
  checkValidity: computed(() => {
    setValidity();
  }),
});

function setValidity() {
  const [isRegErr, isReqErr, settingErr, settingNameErr, pluginErr, id] =
    useCheckPluginsValidity(data.base);

  data.stepErr = id;
  data.isRegErr = isRegErr;
  data.isReqErr = isReqErr;
  data.settingErr = `"${settingNameErr}"`;
}

function updateTemplate(e) {
  if (!e.target.closest("[data-easy-form-step]")) return;
  useUpdateTempSettings(e, data.base);
}

const buttonSave = {
  id: uuidv4(),
  text: "action_save",
  color: "success",
  size: "normal",
  type: "submit",
  containerClass: "flex justify-center",
};

const buttonPrev = {
  id: uuidv4(),
  text: "action_previous",
  color: "info",
  size: "normal",
};

const buttonNext = {
  id: uuidv4(),
  text: "action_next",
  color: "info",
  size: "normal",
};

onMounted(() => {
  // Restart step one every time the component is mounted
  data.currStep = 0;
  setValidity();
  useListenTemp(updateTemplate);
});

onUnmounted(() => {
  useUnlistenTemp(updateTemplate);
});
</script>

<template>
  <Container
    data-easy-form
    :tag="'form'"
    method="POST"
    :containerClass="`form-easy-container`"
    :columns="props.columns"
  >
    <Title type="card" :title="'dashboard_easy_mode'" />
    <Subtitle type="card" :subtitle="'dashboard_easy_mode_subtitle'" />

    <template v-for="(step, id) in data.base">
      <Container
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

        <Container class="form-easy-step-settings-container">
          <template
            v-for="(setting, name, index) in step.settings"
            :key="index"
          >
            <Fields :setting="setting" />
          </template>
        </Container>
      </Container>
    </template>
    <Flex :flexClass="'justify-center'">
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
    </Flex>
    <Text
      v-if="data.isRegErr || data.isReqErr"
      :textClass="'form-setting-error'"
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
  </Container>
</template>
