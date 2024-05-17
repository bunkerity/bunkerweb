<script setup>
import { computed } from 'vue';

/* 
  COMPONENT DESCRIPTION
  *
  *
  This GridLayout component is used at the top level of a page layout.
  This component will determine the position of layout components based on the grid columns.
  We can create card, modal, table and others top level layout using this component.
  The content of this component is grid based.
  *
  *
  PROPS ARGUMENTS
  *
  *
  type : <"card"|"table"|...>  (will determine component style)
  title: string,
  columns : { pc: int, tablet: int, mobile: int},
  gridLayoutClass : <"items-start"|"items-center"|"items-end">
  *
  *
  PROPS EXAMPLE
  *
  *
  type: "card",
  title: "Test",
  columns: { pc: 12, tablet: 12, mobile: 12},
  gridLayoutClass: "items-start"
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
    if(props.type === 'card') return 'bg-white rounded-xl shadow-md w-full';
    return '';
})

const gridClass = computed(() => {
    return `grid grid-cols-12 w-full col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`;
})

const titleClass = computed(() => {
    if(props.type === 'card') return 'text-2xl font-bold mb-2';
    return ''
})
</script>

<template>
<div :class="[containerClass, gridClass, props.gridLayoutClass, 'p-4 m-4']">
    <h1 v-if="props.title" :class="[titleClass, 'col-span-12']">{{ props.title }}</h1>
    <slot></slot>
</div>
</template>
