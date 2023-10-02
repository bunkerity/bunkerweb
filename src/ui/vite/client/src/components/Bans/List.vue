<script setup>
import ListBase from "@components/List/Base.vue";
import ListItem from "@components/List/Item.vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import ButtonBase from "@components/Button/Base.vue";

import {reactive} from "vue";

const props = defineProps({
    items : {
        type: Array
    }
})
</script>

<template>
    <ListBase 
    class="min-w-[1100px] h-full col-span-12"
    :header="listHeader"
    :positions="listPositions"
    >
    <ListItem
    v-for="index, id in props.items"
    :class="[id === index - 1 ? '' : 'border-b']"
    >
    <div class="list-content-item-wrap" >
    
    </div>
    </ListItem>
    </ListBase>
</template>