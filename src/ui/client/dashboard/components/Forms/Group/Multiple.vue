<script setup>
import { reactive, defineProps, defineEmits } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Button from "@components/Widget/Button.vue";
import Fields from "@components/Form/Fields.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Container from "@components/Widget/Container.vue";

/**
 *  @name Forms/Group/Multiple.vue
 *  @description This Will regroup all multiples settings with add and remove logic.
 *  This component under the hood is rendering default fields but by group with possibility to add or remove a multiple group.
 *  @example
 *  {
 *    "columns": {"pc": 6, "tablet": 12, "mobile": 12},
 *      "multiples": {
 *          "reverse-proxy": {
 *              "0": {
 *                  "REVERSE_PROXY_HOST": {
 *                      "context": "multisite",
 *                      "default": "",
 *                      "help": "Full URL of the proxied resource (proxy_pass).",
 *                      "id": "reverse-proxy-host",
 *                      "label": "Reverse proxy host",
 *                      "regex": "^.*$",
 *                      "type": "text",
 *                      "multiple": "reverse-proxy",
 *                      "pattern": "^.*$",
 *                      "inpType": "input",
 *                      "name": "Reverse proxy host",
 *                      "columns": {
 *                          "pc": 4,
 *                          "tablet": 6,
 *                          "mobile": 12
 *                      },
 *                      "disabled": false,
 *                      "value": "service",
 *                      "popovers": [
 *                          {
 *                              "iconName": "disk",
 *                              "text": "inp_popover_multisite"
 *                          },
 *                          {
 *                              "iconName": "info",
 *                              "text": "Full URL of the proxied resource (proxy_pass)."
 *                          }
 *                      ],
 *                      "containerClass": "z-26",
 *                      "method": "ui"
 *                  },
 *                  "REVERSE_PROXY_KEEPALIVE": {
 *                      "context": "multisite",
 *                      "default": "no",
 *                      "help": "Enable or disable keepalive connections with the proxied resource.",
 *                      "id": "reverse-proxy-keepalive",
 *                      "label": "Reverse proxy keepalive",
 *                      "regex": "^(yes|no)$",
 *                      "type": "check",
 *                      "multiple": "reverse-proxy",
 *                      "pattern": "^(yes|no)$",
 *                      "inpType": "checkbox",
 *                      "name": "Reverse proxy keepalive",
 *                      "columns": {
 *                          "pc": 4,
 *                          "tablet": 6,
 *                          "mobile": 12
 *                      },
 *                      "disabled": false,
 *                      "value": "no",
 *                      "popovers": [
 *                          {
 *                              "iconName": "disk",
 *                              "text": "inp_popover_multisite"
 *                          },
 *                          {
 *                              "iconName": "info",
 *                              "text": "Enable or disable keepalive connections with the proxied resource."
 *                          }
 *                      ],
 *                      "containerClass": "z-20"
 *                  },
 *                },
 *              }
 *          }
 *        }
 *    },
 *  @param {Object} multiples - The multiples settings to display. This needs to be a dict of settings using default field format.
 *  @param {Object} [columns={"pc": "12", "tablet": "12", "mobile": "12"}] - Field has a grid system. This allow to get multiple field in the same row if needed.
 *  @param {String} [containerClass=""] - Additionnal class to add to the container
 *  @param {String} [tadId=contentIndex] - The tabindex of the field, by default it is the contentIndex
 */

const props = defineProps({
  // id && value && method
  multiples: {
    type: Object,
    required: false,
    default: {},
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: false,
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  tabId: {
    type: [String, Number],
    required: false,
    default: contentIndex,
  },
});

const multiples = reactive({
  invisible: [],
});

const buttonAdd = {
  text: "action_add",
  color: "success",
  size: "normal",
  type: "button",
  containerClass: "flex justify-center",
};

const buttonToggle = {
  text: "action_toggle",
  color: "info",
  size: "normal",
  type: "button",
  containerClass: "flex justify-center",
};

const buttonDelete = {
  text: "action_remove",
  color: "error",
  size: "normal",
  type: "button",
  containerClass: "flex justify-center",
};

// emits
const emits = defineEmits(["delete", "add"]);

/**
 *  @name setDeleteState
 *  @description Will determine if the group can be deleted. If at least one input is disabled, the delete button will be disabled.
 *  @param {Object} group - The multiple group with all settings
 *  @returns {object} - Return delete button data
 */
function setDeleteState(group) {
  // Loop on group keys and check if at least one input is disabled
  let isDisabled = false;
  for (const [key, value] of Object.entries(group)) {
    if (value.disabled) {
      isDisabled = true;
      break;
    }
  }
  const delBtn = JSON.parse(JSON.stringify(buttonDelete));
  delBtn.disabled = isDisabled;
  return delBtn;
}

/**
 *  @name setInvisible
 *  @description Will set a multiple group as invisible.
 *  @param {String|Number} id - The multiple group with all settings
 *  @returns {Void}
 */
function setInvisible(id) {
  multiples.invisible.push(id);
}

/**
 *  @name delInvisible
 *  @description Will remove a multiple group from invisible list.
 *  @param {String|Number} id - The multiple group with all settings
 *  @returns {Void}
 */
function delInvisible(id) {
  multiples.invisible = multiples.invisible.filter((v) => v !== id);
}

/**
 *  @name toggleVisible
 *  @description Will toggle a multiple group visibility.
 *  @param {String|Number} id - The multiple group with all settings
 *  @returns {Void}
 */
function toggleVisible(id) {
  multiples.invisible.includes(id) ? delInvisible(id) : setInvisible(id);
}

/**
 *  @name delGroup
 *  @description Will emit a delete event to the parent component. The parent will update the template and multiples, then the component will rerender.
 *  @param {String} multName - The multiple group name
 *  @param {String} groupName - The multiple group id
 *  @returns {Void}
 */
function delGroup(multName, groupName) {
  emits("delete", multName, groupName);
}
</script>

<template>
  <template v-for="(multObj, multName, id) in props.multiples">
    <Container
      data-is="multiple"
      class="layout-settings-multiple"
      :columns="props.columns"
      :containerClass="props.containerClass"
    >
      <Container class="col-span-12 flex items-center">
        <Subtitle :subtitle="multName.replaceAll('-', ' ')" />
        <div class="flex justify-center">
          <Button
            v-bind="buttonAdd"
            @click="$emit('add', multName)"
            class="mx-2"
          />
          <Button
            @click="toggleVisible(`${multName}${id}`)"
            v-bind="buttonToggle"
          />
        </div>
      </Container>

      <div
        :aria-hidden="
          multiples.invisible.includes(`${multName}${id}`) ? 'false' : 'true'
        "
        :class="[
          'flex-col-reverse col-span-12',
          multiples.invisible.includes(`${multName}${id}`) ? 'hidden' : 'flex',
        ]"
      >
        <template
          :key="groupName"
          v-for="(group, groupName, groupId) in props.multiples[multName]"
        >
          <Container
            data-group="multiple"
            :data-group-name="groupName"
            :data-mult-name="multName"
            class="layout-settings-multiple-group"
          >
            <Subtitle
              :subtitle="`${multName.replaceAll('-', ' ')} #${+groupName + 1}`"
            />
            <template
              :key="settingName"
              v-for="(setting, settingName, settingId) in group"
            >
              <Fields :setting="setting" />
            </template>
            <div class="col-span-12 flex justify-center">
              <Button
                @click="delGroup(multName, groupName)"
                v-bind="setDeleteState(group)"
              />
            </div>
          </Container>
        </template>
      </div>
    </Container>
  </template>
</template>
