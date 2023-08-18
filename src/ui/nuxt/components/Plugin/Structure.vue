<script setup>
const props = defineProps({
  plugins: {
    type: Array,
  },
  active: {
    type: String,
    required: true,
  },
});

const plug = reactive({
  active: props.active,
});
</script>

<template>
  <div v-for="plugin in props.plugins">
    <PluginContainer :id="plugin.id" v-if="plugin.name === plug.active">
      <PluginHeader
        :id="plugin.id"
        :name="plugin.name"
        :desc="plugin.desc"
        :version="plugin.version"
      />
      <PluginSettingSimple :settings="plugin.setting" />
      <PluginSettingMultiple :settings="plugin.setting" />
    </PluginContainer>
  </div>
</template>
