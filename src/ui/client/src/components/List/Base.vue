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
});
</script>

<template>
  <div role="table" class="list-container">
    <div role="row" class="list-header-container">
      <span
        role="rowheader"
        class="list-header-item"
        v-for="(item, id) in props.header"
        :class="[
          props.positions[id],
          id === header.length - 1 ? 'last' : '',
          id === 0 ? 'first' : '',
        ]"
      >
        {{ item }}
      </span>
    </div>
    <div class="list-content-container">
      <div role="rowgroup" class="list-content-wrap max-h-[300px]">
        <slot></slot>
      </div>
    </div>
  </div>
</template>
