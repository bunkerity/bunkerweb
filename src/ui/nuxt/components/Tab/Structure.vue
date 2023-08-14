<script setup>
const props = defineProps({
  // Tabs to display
  // Prop => [{name : "", desc: ""}]
  list: {
    type: Array,
    required: true,
  },
});

const tab = reactive({
  // Allow to change some style when a tab name is current tab
  current: props.list[0]["name"] || "",
});

// Allow to access tab name from parent
// In order to set additionnal logic
// Like displaying content matching current tabName active
const emits = defineEmits(["tabName"]);

function updateTab(tabName) {
  tab.current = tabName;
  return tabName;
}
</script>

<template>
  <TabContainer>
    <TabItem
      v-for="(item, id) in props.list"
      @click="$emit('tabName', updateTab(item.name))"
      :first="id === 0 ? true : false"
      :last="id === props.list.length - 1 ? true : false"
      :tabName="item.name"
      :desc="item.description"
      :activeTabName="tab.current"
    />
  </TabContainer>
</template>
