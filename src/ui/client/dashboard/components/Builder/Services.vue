<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Table from "@components/Widget/Table.vue";
import Title from "@components/Widget/Title.vue";
import Button from "@components/Widget/Button.vue";
import { useEqualStr } from "@utils/global.js";

/**
  @name Builder/Services.vue
  @description This component is lightweight builder containing only the necessary components to create the services page.
  @example
[
    {
        "type": "card",
        "containerColumns": {
            "pc": 12,
            "tablet": 12,
            "mobile": 12
        },
        "widgets": [
            {
                "type": "Title",
                "data": {
                    "title": "services_title"
                }
            },
            {
                "type": "Table",
                "data": {
                    "title": "services_table_title",
                    "minWidth": "lg",
                    "header": [
                        "services_table_name",
                        "services_table_method",
                        "services_table_settings",
                        "services_table_manage",
                        "services_table_is_draft",
                        "services_table_delete"
                    ],
                    "positions": [
                        2,
                        2,
                        2,
                        2,
                        2,
                        2
                    ],
                    "items": [
                        [
                            {
                                "name": "app1.example.com",
                                "type": "Text",
                                "data": {
                                    "text": "app1.example.com"
                                }
                            },
                            {
                                "method": "scheduler",
                                "type": "Text",
                                "data": {
                                    "text": "scheduler"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "id": "open-modal-settings-0",
                                    "text": "settings",
                                    "hideText": false,
                                    " color": "info",
                                    "size": "normal",
                                    "iconName": "settings"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "app1.example.com"
                                    },
                                    "id": "open-modal-manage-0",
                                    "text": "manage",
                                    "hideText": false,
                                    " color": "green",
                                    "size": "normal",
                                    "iconName": "manage"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "app1.example.com",
                                        "data-is-draft": "no"
                                    },
                                    "id": "open-modal-draft-0",
                                    "text": "online",
                                    "hideText": false,
                                    " color": "cyan",
                                    "size": "normal",
                                    "iconName": "online"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "app1.example.com"
                                    },
                                    "id": "open-modal-delete-0",
                                    "text": "delete",
                                    "disabled": true,
                                    "hideText": false,
                                    " color": "red",
                                    "size": "normal",
                                    "iconName": "trash"
                                }
                            }
                        ],
                        [
                            {
                                "name": "www.example.com",
                                "type": "Text",
                                "data": {
                                    "text": "www.example.com"
                                }
                            },
                            {
                                "method": "scheduler",
                                "type": "Text",
                                "data": {
                                    "text": "scheduler"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "id": "open-modal-settings-1",
                                    "text": "settings",
                                    "hideText": false,
                                    " color": "info",
                                    "size": "normal",
                                    "iconName": "settings"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "www.example.com"
                                    },
                                    "id": "open-modal-manage-1",
                                    "text": "manage",
                                    "hideText": false,
                                    " color": "green",
                                    "size": "normal",
                                    "iconName": "manage"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "www.example.com",
                                        "data-is-draft": "no"
                                    },
                                    "id": "open-modal-draft-1",
                                    "text": "online",
                                    "hideText": false,
                                    " color": "cyan",
                                    "size": "normal",
                                    "iconName": "online"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "www.example.com"
                                    },
                                    "id": "open-modal-delete-1",
                                    "text": "delete",
                                    "disabled": true,
                                    "hideText": false,
                                    " color": "red",
                                    "size": "normal",
                                    "iconName": "trash"
                                }
                            }
                        ]
                    ],
                    "filters": [
                        {
                            "filter": "table",
                            "filterName": "keyword",
                            "type": "keyword",
                            "value": "",
                            "keys": [
                                "name"
                            ],
                            "field": {
                                "id": "services-keyword",
                                "value": "",
                                "type": "text",
                                "name": "services-keyword",
                                "label": "services_search",
                                "placeholder": "inp_keyword",
                                "isClipboard": false,
                                "popovers": [
                                    {
                                        "text": "services_search_desc",
                                        "iconName": "info"
                                    }
                                ],
                                "columns": {
                                    "pc": 3,
                                    "tablet": 4,
                                    "mobile": 12
                                }
                            }
                        },
                        {
                            "filter": "table",
                            "filterName": "method",
                            "type": "select",
                            "value": "all",
                            "keys": [
                                "method"
                            ],
                            "field": {
                                "id": "services-methods",
                                "value": "all",
                                "values": [
                                    "scheduler"
                                ],
                                "name": "services-methods",
                                "onlyDown": true,
                                "label": "services_methods",
                                "popovers": [
                                    {
                                        "text": "services_methods_desc",
                                        "iconName": "info"
                                    }
                                ],
                                "columns": {
                                    "pc": 3,
                                    "tablet": 4,
                                    "mobile": 12
                                }
                            }
                        },
                        {
                            "filter": "table",
                            "filterName": "draft",
                            "type": "select",
                            "value": "all",
                            "keys": [
                                "draft"
                            ],
                            "field": {
                                "id": "services-draft",
                                "value": "all",
                                "values": [
                                    "all",
                                    "online",
                                    "draft"
                                ],
                                "name": "services-draft",
                                "onlyDown": true,
                                "label": "services_draft",
                                "popovers": [
                                    {
                                        "text": "services_draft_desc",
                                        "iconName": "info"
                                    }
                                ],
                                "columns": {
                                    "pc": 3,
                                    "tablet": 4,
                                    "mobile": 12
                                }
                            }
                        }
                    ]
                }
            }
        ]
    }
]
  @param {array} builder - Array of containers and widgets
*/

const props = defineProps({
  builder: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <!-- top level grid (layout) -->
  <GridLayout
    v-for="(container, index) in props.builder"
    :key="index"
    :gridLayoutClass="container.containerClass"
    :type="container.type"
    :title="container.title"
    :link="container.link"
    :columns="container.containerColumns"
    :id="container.id"
  >
    <!-- widget grid -->
    <Grid>
      <!-- widget element -->
      <template v-for="(widget, index) in container.widgets" :key="index">
        <Table v-if="useEqualStr(widget.type, 'Table')" v-bind="widget.data" />
        <Button
          v-if="useEqualStr(widget.type, 'Button')"
          v-bind="widget.data"
        />
        <Title v-if="useEqualStr(widget.type, 'Title')" v-bind="widget.data" />
      </template>
    </Grid>
  </GridLayout>
</template>
