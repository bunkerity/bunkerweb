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
</script>

<template>
  <div
    class="col-span-12 max-h-[65vh] overflow-y-auto overflow-x-hidden"
    v-for="plugin in props.plugins"
  >
    <PluginContainer :id="plugin.id" v-if="plugin.name === props.active">
      <PluginHeader
        :id="plugin.id"
        :name="plugin.name"
        :desc="plugin.description"
        :version="plugin.version"
      />
      <div class="grid grid-cols-12">
        <PluginSettingSimple :settings="plugin.settings" />
        <PluginSettingMultiple :settings="plugin.settings" />
      </div>
    </PluginContainer>
  </div>
</template>
