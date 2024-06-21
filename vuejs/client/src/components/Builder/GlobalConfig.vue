<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Templates from "@components/Form/Templates.vue";

/**
  @name Builder/GlobalConfig.vue
  @description This component is lightweight builder containing only the necessary components to create the instances page.
  @example
  [
  {
    type: "card",
    containerColumns: { pc: 12, tablet: 12, mobile: 12 },
    widgets: [
    {
    type: "Title",
    data : {
      title: "dashboard_global_config",
      type: "card"
    },
    },
      {
        type: "Templates",
        data: {
          title: "home_version",
          subtitle: "home_all_features_available" if is_pro_version else "home_upgrade_pro",
          subtitleColor: "success" is is_pro_version else "warning",
          stat: "home_pro" if is_pro_version else "home_free",
          iconName: "crown" if is_pro_version else "core",
          iconColor: "amber",
        },
      },
    ],
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
        <Title v-if="widget.type === 'Title'" v-bind="widget.data" />
        <Subtitle v-if="widget.type === 'Subtitle'" v-bind="widget.data" />
        <Templates v-if="widget.type === 'Templates'" v-bind="widget.data" />
      </template>
    </Grid>
  </GridLayout>
</template>
