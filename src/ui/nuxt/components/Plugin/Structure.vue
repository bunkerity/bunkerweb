<script setup>
const props = defineProps({
  configs: {
    type: Array,
  },
});

const config = reactive({
  activeInstance: props.configs[0].instance,
  activePlugin: "",
});

// NEED TO ADD INSTANCE TAB TO SWITCH
</script>

<template>
  <div v-for="config in props.configs">
    <div v-if="config.instance === config.activeInstance">
      <PluginContainer
        :id="config.id"
        :name="config.name"
        :activePlugin="config.activePlugin"
      >
        <PluginHeader
          :id="config.id"
          :name="config.name"
          :desc="config.desc"
          :version="props.version"
        />
        <PluginSettingSimple :settings="config.setting" />
        <PluginSettingMultiple :settings="config.setting" />
      </PluginContainer>
    </div>
  </div>
</template>
