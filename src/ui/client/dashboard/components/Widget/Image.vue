<script setup>
import { onMounted, reactive, ref } from "vue";

/**
 *  @name Widget/Image.vue
 *  @description This component is used for regular paragraph.
 *  @example
 *  {
 *    src: "https://via.placeholder.com/150",
 *    alt: "My image",
 *    attrs: { id: "paragraph" },
 *  }
 *  @param {String} src - The src value of the image.
 *  @param {String} [alt=""] - The alt value of the image.  Can be a translation key or by default raw text.
 *  @param {String} [imgClass=""]
 *  @param {String} [imgContainerClass=""]
 *  @param {Object} [attrs={}] - List of attributes to add to the image.
 */

const props = defineProps({
  src: {
    type: [String, Number],
    required: true,
  },
  alt: {
    type: String,
    required: false,
    default: "",
  },
  imgClass: {
    type: String,
    required: false,
    default: "h-full w-full",
  },
  imgContainerClass: {
    type: String,
    required: false,
    default: "flex justify-center items-center h-48 w-48",
  },
  attrs: {
    type: Object,
    required: false,
    default: {},
  },
});
</script>

<template>
  <div v-if="props.src" :class="[props.imgContainerClass]">
    <img
      :alt="$t(props.alt, $t('dashboard_placeholder', props.alt))"
      v-bind="props.attrs"
      :class="[props.imgClass]"
    />
  </div>
</template>
