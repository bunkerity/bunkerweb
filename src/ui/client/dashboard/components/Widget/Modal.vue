<script setup>
import {
  defineProps,
  defineEmits,
  Teleport,
  ref,
  watch,
  onMounted,
  onUnmounted,
} from "vue";
import { useEqualStr } from "@utils/global.js";
// Containers
import Grid from "@components/Widget/Grid.vue";
import Title from "@components/Widget/Title.vue";
import Text from "@components/Widget/Text.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import MessageUnmatch from "@components/Message/Unmatch.vue";

/**
  @name Builder/Modal.vue
  @description This component contains all widgets needed on a modal.
  This is different from a page builder as we don't need to define the container and grid layout.
  We can't create multiple grids or containers in a modal.
  @example
[
  "id": "modal-delete-plugin",
  "widgets": [
      {
          "type": "Title",
          "data": {
              "title": "plugins_modal_delete_title",
              "type": "modal"
          }
      },
      {
          "type": "Text",
          "data": {
              "text": "plugins_modal_delete_confirm"
          }
      },
      {
          "type": "Text",
          "data": {
              "text": "",
              "bold": true,
              "attrs": {
                  "data-modal-plugin-name": "true"
              }
          }
      },
      {
          "type": "ButtonGroup",
          "data": {
              "buttons": [
                  {
                      "id": "delete-plugin-btn",
                      "text": "action_close",
                      "disabled": false,
                      "color": "close",
                      "size": "normal",
                      "attrs": {
                          "data-hide-el": "modal-delete-plugin"
                      }
                  },
                  {
                      "id": "delete-plugin-btn",
                      "text": "action_delete",
                      "disabled": false,
                      "color": "delete",
                      "size": "normal",
                      "attrs": {
                          "data-delete-plugin-submit": ""
                      }
                  }
              ],
          }
      }
  ]
];
  @param {array} widgets - Array of containers and widgets
*/

const props = defineProps({
  id: {
    type: String,
    required: false,
    default: "",
  },
  widgets: {
    type: Object,
    required: true,
  },
  isOpen: {
    type: Boolean,
    required: false,
    default: false,
  },
});

const modalEl = ref();

function useCloseModal() {
  emits("close");
}

/**
  @name useFocusModal
  @description Check if the modal is present and a focusable element is present inside it.
  If it's the case, the function will focus the element.
  Case there is already a focused element inside the modal, avoid to focus it again.
  @param {string} modalId - The id of the modal element.
  @returns {void}
*/
function useFocusModal() {
  setTimeout(() => {
    if (!modalEl.value) return;
    // Get the current active element
    const activeEl = document.activeElement;
    // Check if the active element is inside the modal
    if (modalEl.value.contains(activeEl)) return;
    // Case not, focus first focusable element inside the modal
    const focusable = modalEl.value.querySelector("[tabindex]");
    if (focusable) focusable.focus();
  }, 1);
}

function modalKeyboardEvents(e) {
  if (e.key === "Escape") useCloseModal();
  if (e.key === "Tab" || e.key === "Shift-Tab") useFocusModal();
}

function modalClickEvents(e) {
  if (e.target.closest("[data-modal]") !== modalEl.value && modalEl.value)
    return;
  if (e.target.hasAttribute("data-close-modal")) useCloseModal();
}

function setEvents() {
  window.addEventListener("keydown", modalKeyboardEvents, true);
  window.addEventListener("click", modalClickEvents);
}

function unsetEvents() {
  window.removeEventListener("keydown", modalKeyboardEvents, true);
  window.removeEventListener("click", modalClickEvents);
}

onMounted(() => {
  setEvents();
});

onUnmounted(() => {
  unsetEvents();
});

const emits = defineEmits(["close"]);
</script>

<template>
  <Teleport to="#app">
    <div
      ref="modalEl"
      :data-is="'modal'"
      data-modal
      :class="['layout-modal-container', props.isOpen ? '' : 'hidden']"
      :id="props.id"
    >
      <div data-close-modal class="layout-backdrop"></div>
      <div class="layout-modal-wrap">
        <div class="layout-modal">
          <div class="layout-modal-button-container">
            <Button
              data-close-modal
              :text="'action_close_modal'"
              :hideText="true"
              :iconName="'close'"
              :color="'transparent'"
            />
          </div>
          <Grid>
            <!-- widget element -->
            <template v-for="(widget, index) in props.widgets">
              <MessageUnmatch
                v-if="useEqualStr(widget.type, 'MessageUnmatch')"
                v-bind="widget.data"
              />
              <Title
                v-if="useEqualStr(widget.type, 'Title')"
                v-bind="widget.data"
              />
              <Text
                v-if="useEqualStr(widget.type, 'Text')"
                v-bind="widget.data"
              />
              <Subtitle
                v-if="useEqualStr(widget.type, 'Subtitle')"
                v-bind="widget.data"
              />
              <Button
                v-if="useEqualStr(widget.type, 'Button')"
                v-bind="widget.data"
              />
              <ButtonGroup
                v-if="useEqualStr(widget.type, 'ButtonGroup')"
                v-bind="widget.data"
              />
            </template>
          </Grid>
        </div>
      </div>
    </div>
  </Teleport>
</template>
