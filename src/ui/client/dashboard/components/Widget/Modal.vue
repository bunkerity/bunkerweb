<script setup>
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
  widgets: {
    type: Array,
    required: true,
  },
  isOpen: {
    type: Boolean,
    required: false,
    default: false,
  },
});
</script>

<template>
  <div
    :data-is="'modal'"
    data-modal
    :class="['layout-modal-container', props.isOpen ? '' : 'hidden']"
    class="layout-modal-container hidden"
    :id="props.id"
  >
    <div class="layout-backdrop"></div>
    <div class="layout-modal-wrap" :data-hide-el="props.id">
      <div class="layout-modal">
        <div class="layout-modal-button-container">
          <Button
            :attrs="{ 'data-hide-el': props.id }"
            :text="'action_close_modal'"
            :hideText="true"
            :iconName="'close'"
            :color="'transparent'"
          />
        </div>
        <Grid>
          <!-- widget element -->
          <template v-for="(widget, index) in props.widgets" :key="index">
            <MessageUnmatch
              v-if="widget.type.toLowerCase() === 'messageunmatch'"
              v-bind="widget.data"
            />
            <Title
              v-if="widget.type.toLowerCase() === 'title'"
              v-bind="widget.data"
            />
            <Text
              v-if="widget.type.toLowerCase() === 'text'"
              v-bind="widget.data"
            />
            <Subtitle
              v-if="widget.type.toLowerCase() === 'subtitle'"
              v-bind="widget.data"
            />
            <Button
              v-if="widget.type.toLowerCase() === 'button'"
              v-bind="widget.data"
            />
            <ButtonGroup
              v-if="widget.type.toLowerCase() === 'buttongroup'"
              v-bind="widget.data"
            />
          </template>
        </Grid>
      </div>
    </div>
  </div>
</template>
