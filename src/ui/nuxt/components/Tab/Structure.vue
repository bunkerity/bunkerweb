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

const tab = reactive({
  // Allow to change some style when a tab name is current tab
  active: props.active,
});

// Allow to access tab name from parent
// In order to set additionnal logic
// Like displaying content matching current tabName active
const emits = defineEmits(["tabName"]);

function updateTab(tabName) {
  tab.active = tabName;
  return tabName;
}
</script>

<template>
  <TabContainer>
    <TabItem
      v-for="(item, id) in props.items"
      @click="$emit('tabName', updateTab(item.name))"
      :first="id === 0 ? true : false"
      :last="id === props.items.length - 1 ? true : false"
      :tabName="item.name"
      :desc="item.description"
      :activeTabName="tab.active"
    />
  </TabContainer>
</template>
