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
  <section class="list-container">
    <div class="list-header-container">
      <label
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
