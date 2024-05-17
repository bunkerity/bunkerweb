<script setup>
import { computed } from 'vue';

/* 
  This GridLayout component is used at the top level of a page layout.
  This component will determine the position of layout components based on the grid columns.
  We can create card, modal, table and others top level layout using this component.
  The content of this component is grid based.

  PROPS ARGUMENTS
  *
  *
  type : <"card"|"table"|...>  (will determine component style)
  title: string,
  columns : { pc: int, tablet: int, mobile: int},
  verticalAlign : <"items-start"|"items-center"|"items-end">
  *
  *
*/

const props = defineProps({
    type : {
        type: String,
        required: false,
        default : "grid"
    },
    title : {
        type: String,
        required: false,
        default : ""
    },
    columns : {
        type: Object,
        required: false,
        default : {
            pc: 12,
            tablet: 12,
            mobile: 12}
    },
    gridLayoutClass : {
        type: String,
        required: false,
        default: "items-start"
    },

})

const containerClass = computed(() => {
    if(props.type === 'card') return 'bg-white rounded shadow-md w-full';
    return '';
})

const gridClass = computed(() => {
    return `grid grid-cols-12 w-full col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`;
})

const titleClass = computed(() => {
    if(props.type === 'card') return 'text-2xl font-bold text-center m-4';
    return ''
})
</script>

<template>
<div :class="[containerClass, gridClass, props.gridLayoutClass]">
    <h1 v-if="props.title" :class="[titleClass]">{{ props.title }}</h1>
    <slot></slot>
</div>
</template>
