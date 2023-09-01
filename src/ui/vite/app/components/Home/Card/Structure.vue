<script setup>
import HomeCardHeader from "../../Home/Card/Header.vue";
import HomeCardDetails from "../../Home/Card/Details.vue";
const props = defineProps({
  href: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  count: {
    type: Number,
    required: true,
  },
  detailArr: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <a :href="props.href ? props.href : '#'" class="card-stat">
    <div>
      <HomeCardHeader :name="props.name" :count="props.count" />
      <HomeCardDetails :detailArr="props.detailArr" />
    </div>

    <slot></slot>
  </a>
</template>
