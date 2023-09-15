<script setup>
import PluginContainer from "@components/Plugin/Container.vue";
import PluginHeader from "@components/Plugin/Header.vue";
import PluginSettingSimple from "@components/Plugin/Setting/Simple.vue";
import PluginSettingMultiple from "@components/Plugin/Setting/Multiple.vue";
import { defineProps, onMounted } from "vue";

const props = defineProps({
  plugins: {
    type: Array,
  },
  active: {
    type: String,
    required: true,
  },
  serviceName: {
    type: String,
    required: false,
    default: "",
  },
});

onMounted(() => console.log(props.plugins));
</script>

<template>
  <div
    class="plugin-structure col-span-12 max-h-[65vh] overflow-y-auto overflow-x-hidden"
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
        <PluginSettingSimple
          :serviceName="props.serviceName"
          :settings="plugin.settings"
        />
        <PluginSettingMultiple
          :serviceName="props.serviceName"
          :settings="plugin.settings"
        />
      </div>
    </PluginContainer>
  </div>
</template>
