<script setup>
import Dashboard from "../../layouts/Dashboard.vue";
import CardBase from "../../components/Card/Base.vue";
import CardItemList from "../../components/Card/Item/List.vue";
import SettingsLayout from "../../components/Settings/Layout.vue";
import SettingsInput from "../../components/Settings/Input.vue";
import SettingsSelect from "../../components/Settings/Select.vue";
import TableStructure from "../../components/Table/Structure.vue";
</script>

<template>
  <Dashboard>
    <CardBase
      class="h-fit col-span-12 md:col-span-4 2xl:col-span-3 3xl:col-span-2"
      title="info"
    >
      <CardItemList
        :items="[
          { label: 'jobs total', value: '12' },
          { label: 'jobs errors', value: '1' },
        ]"
      />
    </CardBase>
    <CardBase
      class="z-10 h-fit col-span-12 md:col-span-8 xl:col-span-8 2xl:col-span-5 3xl:col-span-4"
      title="filter"
    >
      <SettingsLayout title="Search" name="keyword">
        <SettingsInput
          :setting="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: 'keyword',
          }"
        />
      </SettingsLayout>
      <SettingsLayout title="Success state" name="state">
        <SettingsSelect
          :setting="{
            id: 'state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </SettingsLayout>
      <SettingsLayout title="Success state" name="state">
        <SettingsSelect
          :setting="{
            id: 'state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </SettingsLayout>
    </CardBase>
    <CardBase
      class="col-span-12 overflow-x-auto overflow-y-visible"
      title="jobs"
    >
      <TableStructure />
    </CardBase>
  </Dashboard>
</template>
