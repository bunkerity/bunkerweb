<script setup>
import ListItem from "@components/List/Item.vue";
import { defineProps } from "vue";
const props = defineProps({
  items: {
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
  <ListItem
    v-for="(item, id) in props.items"
    :class="[id === props.items.length - 1 ? '' : 'border-b']"
  >
    <div class="list-content-item-wrap" v-for="(data, key) in item">
      <span class="pl-4" :class="[props.positions[0]]">{{
        data["method"]
      }}</span>
      <span :class="[props.positions[1]]">{{ data["title"] }}</span>
      <span :class="[props.positions[1]]">{{ data["text"] }}</span>
      <span :class="[props.positions[1]]">{{ data["date"] }}</span>
    </div>
  </ListItem>
</template>
