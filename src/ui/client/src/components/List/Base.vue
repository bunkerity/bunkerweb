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
  <section role="table" class="list-container">
    <div role="rowgroup" class="list-header-container">
      <label
        role="rowheader"
        :aria-rowcount="id"
        class="list-header-item"
        v-for="(item, id) in props.header"
        :class="[
          props.positions[id],
          id === header.length - 1 ? 'last' : '',
          id === 0 ? 'first' : '',
        ]"
      >
        {{ item }}
      </label>
    </div>
    <div class="list-content-container">
      <ul class="list-content-wrap max-h-[300px]">
        <slot></slot>
      </ul>
    </div>
  </section>
</template>
