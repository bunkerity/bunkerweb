<script setup>
import HomeCardHeader from "@components/Home/Card/Header.vue";
import HomeCardDetails from "@components/Home/Card/Details.vue";
import { defineProps } from "vue";

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
    type: [Number, String],
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
