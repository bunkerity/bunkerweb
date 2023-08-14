<script setup>
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
    type: String,
    required: true,
  },
  detailArr: {
    type: Array,
    required: true,
  },
  svgCtnrClass: {
    type: String,
    required: true,
  },
});
</script>

<template>
  <a :href="props.href ? props.href : '#'" class="card-stat">
    <div>
      <p class="card-stat-title">{{ props.name ? props.name : "none" }}</p>
      <h5 class="card-stat-count">
        {{ props.count ? props.count : "none" }}
      </h5>
      <!-- details -->
      <span
        v-for="detail in props.detailArr"
        class="card-stat-detail-container-item"
      >
        <span
          v-if="detail.num"
          :class="[
            detail.numClass
              ? detail.numClass
              : 'text-gray-700 dark:text-gray-500',
          ]"
        >
          {{ detail.num }}
        </span>
        <span
          v-if="detail.text"
          :class="[
            detail.textClass
              ? detail.textClass
              : 'text-gray-700 dark:text-gray-500',
          ]"
        >
          {{ ` ${detail.text}` }}
        </span>
      </span>
    </div>

    <div
      :class="[
        props.svgCtnrClass ? props.svgCtnrClass : 'bg-green-500',
        `card-stat-svg-container`,
      ]"
    >
      <slot></slot>
    </div>
  </a>
</template>
