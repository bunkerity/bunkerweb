<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Table from "@components/Widget/Table.vue";
import Title from "@components/Widget/Title.vue";

/**
  @name Builder/Jobs.vue
  @description This component is lightweight builder containing only the necessary components to create the jobs page.
  @example
[
    {
        "type": "card",
        "containerColumns": {
            "pc": 4,
            "tablet": 6,
            "mobile": 12
        },
        "widgets": [
            {
                "type": "table",
                "data": {
                    "title": "jobs_table_title",
                    "minWidth": "lg",
                    "header": [
                        "jobs_table_name",
                        "jobs_table_plugin_id",
                        "jobs_table_interval",
                        "jobs_table_last_run",
                        "jobs_table_success",
                        "jobs_table_last_run_date",
                        "jobs_table_cache"
                    ],
                    "positions": [
                        2,
                        2,
                        1,
                        1,
                        1,
                        3,
                        2
                    ],
                    "items": [
                        [
                            {
                                "name": "anonymous-report",
                                "type": "Text",
                                "data": {
                                    "text": "anonymous-report"
                                }
                            },
                        ],
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
  >
    <!-- widget grid -->
    <Grid>
      <!-- widget element -->
      <template v-for="(widget, index) in container.widgets" :key="index">
        <Table v-if="widget.type === 'Table'" v-bind="widget.data" />
        <Title v-if="widget.type === 'Title'" v-bind="widget.data" />
      </template>
    </Grid>
  </GridLayout>
</template>
