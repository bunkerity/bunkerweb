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
        :class="[
          props.positions[id],
          id === header.length - 1 ? 'last' : '',
          id === 0 ? 'first' : '',
        ]"
      >
        <th class="block" role="columnheader">
          {{ item }}
        </th>
      </tr>
    </thead>
    <tbody class="list-content-container">
      <slot></slot>
    </tbody>
  </table>
</template>
