<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Instance from "@components/Widget/Instance.vue";

/**
  @name Builder/Instances.vue
  @description This component is lightweight builder containing only the necessary components to create the instances page.
  @example
  [
{
        type: "Instance",
        data: {
          details: [
            { key: <instances_hostname="hostname">, value: "www.example.com" },
            { key: <instances_method="method">, value: <dashboard_ui> or <dashboard_scheduler>...},
            { key: <instances_port="port">, value: "1084" },
            { key: <instances_status="status">, value: <instances_active="active"> or <instances_inactive="inactive"> },
          ],
          status: "success",
          title: "www.example.com",
          buttons: [
            {
              text: <action_*>,
              color: "edit",
              size: "normal",
            },
          ],
        },
      },
];
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
        <Instance
          v-if="widget.type.toLowerCase() === 'instance'"
          v-bind="widget.data"
        />
      </template>
    </Grid>
  </GridLayout>
</template>
