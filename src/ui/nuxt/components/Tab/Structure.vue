<script setup>
const props = defineProps({
  // Tabs to display
  // Prop => [{name : "", desc: ""}]
  items: {
    type: Array,
    required: true,
  },
  active: {
    type: String,
    required: true,
  },
});

// Allow to access tab name from parent
// In order to set additionnal logic
// Like displaying content matching current tabName active
const emits = defineEmits(["tabName"]);
</script>

<template>
  <TabContainer>
    <TabItem
      v-for="(item, id) in props.items"
      @click="$emit('tabName', item.name)"
      :first="id === 0 ? true : false"
      :last="id === props.items.length - 1 ? true : false"
      :name="item.name"
      :desc="item.description"
      :active="props.active"
    />
  </TabContainer>
</template>
