<script setup>
const props = defineProps({
  header: {
    type: Array,
    required: true,
  },
  positions: {
    type: Array,
    required: true,
  },
  summary: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <table :summary="props.summary" class="list-container">
    <thead class="list-header-container">
      <tr
        class="list-header-item"
        v-for="(item, id) in props.header"
        :class="[props.positions[id]]"
      >
        <th role="columnheader">
          {{ item }}
        </th>
      </tr>
    </thead>
    <tbody tabindex="-1" class="list-content-container">
      <slot></slot>
    </tbody>
  </table>
</template>
