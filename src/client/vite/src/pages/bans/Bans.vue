<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderBans from "@components/Builder/Bans.vue";
import { useGlobal } from "@utils/global.js";
import { useForm } from "@utils/form.js";

/**
  @name Page/Bans.vue
  @description This component is the ban page.
  This page displays global information about bans, and allow to delete or upload some bans.
*/

const bans = reactive({
  builder: "",
});

onBeforeMount(() => {
  // Get builder data
  const dataAtt = "data-server-builder";
  const dataEl = document.querySelector(`[${dataAtt}]`);
  const data =
    dataEl && !dataEl.getAttribute(dataAtt).includes(dataAtt)
      ? JSON.parse(dataEl.getAttribute(dataAtt))
      : {};
  bans.builder = data;
});

onMounted(() => {
  useGlobal();
  useForm();
});

const builder = [
  {
    type: "void",
    widgets: [
      {
        type: "Button",
        data: {
          text: "bans_not_found",
        },
      },
    ],
  },
  {
    type: "card",
    containerColumns: {
      pc: 12,
      tablet: 12,
      mobile: 12,
    },
    widgets: [
      {
        type: "Title",
        data: {
          title: "bans_title",
        },
      },
      {
        type: "Table",
        data: {
          title: "bans_table_title",
          minWidth: "xl",
          header: [
            "bans_table_select",
            "bans_table_ip",
            "bans_table_reason",
            "bans_table_ban_start",
            "bans_table_ban_end",
            "bans_table_remain",
            "bans_table_term",
          ],
          positions: [1, 1, 1, 3, 3, 2, 1],
          items: [
            [
              {
                select: false,
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: false,
                    value: "no",
                    inpType: "checkbox",
                    id: "select-ban-1",
                    name: "select-ban-1",
                    label: "select-ban-1",
                    hideLabel: true,
                  },
                },
              },
              {
                ip: "127.0.0.1",
                type: "Text",
                data: {
                  text: "127.0.0.1",
                },
              },
              {
                reason: "ui",
                type: "Text",
                data: {
                  text: "ui",
                },
              },
              {
                ban_start: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-start-1",
                    name: "datepicker-ban-ban-start-1",
                    label: "datepicker-ban-ban-start-1",
                    hideLabel: true,
                  },
                },
              },
              {
                ban_end: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-end-1",
                    name: "datepicker-ban-ban-end-1",
                    label: "datepicker-ban-ban-end-1",
                    hideLabel: true,
                  },
                },
              },
              {
                remain: "23 hours and 49 minutes",
                type: "Text",
                data: {
                  text: "23 hours and 49 minutes",
                },
              },
              {
                term: "hour(s)",
                type: "Text",
                data: {
                  text: "hour(s)",
                },
              },
            ],
            [
              {
                select: false,
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: false,
                    value: "no",
                    inpType: "checkbox",
                    id: "select-ban-2",
                    name: "select-ban-2",
                    label: "select-ban-2",
                    hideLabel: true,
                  },
                },
              },
              {
                ip: "127.0.0.1",
                type: "Text",
                data: {
                  text: "127.0.0.1",
                },
              },
              {
                reason: "ui",
                type: "Text",
                data: {
                  text: "ui",
                },
              },
              {
                ban_start: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-start-2",
                    name: "datepicker-ban-ban-start-2",
                    label: "datepicker-ban-ban-start-2",
                    hideLabel: true,
                  },
                },
              },
              {
                ban_end: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-end-2",
                    name: "datepicker-ban-ban-end-2",
                    label: "datepicker-ban-ban-end-2",
                    hideLabel: true,
                  },
                },
              },
              {
                remain: "23 hours and 49 minutes",
                type: "Text",
                data: {
                  text: "23 hours and 49 minutes",
                },
              },
              {
                term: "day(s)",
                type: "Text",
                data: {
                  text: "day(s)",
                },
              },
            ],
            [
              {
                select: false,
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: false,
                    value: "no",
                    inpType: "checkbox",
                    id: "select-ban-3",
                    name: "select-ban-3",
                    label: "select-ban-3",
                    hideLabel: true,
                  },
                },
              },
              {
                ip: "127.0.0.1",
                type: "Text",
                data: {
                  text: "127.0.0.1",
                },
              },
              {
                reason: "cor",
                type: "Text",
                data: {
                  text: "cor",
                },
              },
              {
                ban_start: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-start-3",
                    name: "datepicker-ban-ban-start-3",
                    label: "datepicker-ban-ban-start-3",
                    hideLabel: true,
                  },
                },
              },
              {
                ban_end: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-end-3",
                    name: "datepicker-ban-ban-end-3",
                    label: "datepicker-ban-ban-end-3",
                    hideLabel: true,
                  },
                },
              },
              {
                remain: "23 hours and 49 minutes",
                type: "Text",
                data: {
                  text: "23 hours and 49 minutes",
                },
              },
              {
                term: "hour(s)",
                type: "Text",
                data: {
                  text: "hour(s)",
                },
              },
            ],
            [
              {
                select: false,
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: false,
                    value: "no",
                    inpType: "checkbox",
                    id: "select-ban-4",
                    name: "select-ban-4",
                    label: "select-ban-4",
                    hideLabel: true,
                  },
                },
              },
              {
                ip: "127.0.0.1",
                type: "Text",
                data: {
                  text: "127.0.0.1",
                },
              },
              {
                reason: "ui",
                type: "Text",
                data: {
                  text: "ui",
                },
              },
              {
                ban_start: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-start-4",
                    name: "datepicker-ban-ban-start-4",
                    label: "datepicker-ban-ban-start-4",
                    hideLabel: true,
                  },
                },
              },
              {
                ban_end: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-end-4",
                    name: "datepicker-ban-ban-end-4",
                    label: "datepicker-ban-ban-end-4",
                    hideLabel: true,
                  },
                },
              },
              {
                remain: "23 hours and 49 minutes",
                type: "Text",
                data: {
                  text: "23 hours and 49 minutes",
                },
              },
              {
                term: "hour(s)",
                type: "Text",
                data: {
                  text: "hour(s)",
                },
              },
            ],
            [
              {
                select: false,
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: false,
                    value: "no",
                    inpType: "checkbox",
                    id: "select-ban-5",
                    name: "select-ban-5",
                    label: "select-ban-5",
                    hideLabel: true,
                  },
                },
              },
              {
                ip: "127.0.0.1",
                type: "Text",
                data: {
                  text: "127.0.0.1",
                },
              },
              {
                reason: "ui",
                type: "Text",
                data: {
                  text: "ui",
                },
              },
              {
                ban_start: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-start-5",
                    name: "datepicker-ban-ban-start-5",
                    label: "datepicker-ban-ban-start-5",
                    hideLabel: true,
                  },
                },
              },
              {
                ban_end: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-end-5",
                    name: "datepicker-ban-ban-end-5",
                    label: "datepicker-ban-ban-end-5",
                    hideLabel: true,
                  },
                },
              },
              {
                remain: "23 hours and 49 minutes",
                type: "Text",
                data: {
                  text: "23 hours and 49 minutes",
                },
              },
              {
                term: "hour(s)",
                type: "Text",
                data: {
                  text: "hour(s)",
                },
              },
            ],
            [
              {
                select: false,
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: false,
                    value: "no",
                    inpType: "checkbox",
                    id: "select-ban-6",
                    name: "select-ban-6",
                    label: "select-ban-6",
                    hideLabel: true,
                  },
                },
              },
              {
                ip: "127.0.0.1",
                type: "Text",
                data: {
                  text: "127.0.0.1",
                },
              },
              {
                reason: "ui",
                type: "Text",
                data: {
                  text: "ui",
                },
              },
              {
                ban_start: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-start-6",
                    name: "datepicker-ban-ban-start-6",
                    label: "datepicker-ban-ban-start-6",
                    hideLabel: true,
                  },
                },
              },
              {
                ban_end: "1719393920",
                type: "Fields",
                data: {
                  setting: {
                    columns: {
                      pc: 12,
                      tablet: 12,
                      mobile: 12,
                    },
                    disabled: true,
                    value: 1719393920,
                    inpType: "datepicker",
                    id: "datepicker-ban-ban-end-6",
                    name: "datepicker-ban-ban-end-6",
                    label: "datepicker-ban-ban-end-6",
                    hideLabel: true,
                  },
                },
              },
              {
                remain: "23 hours and 49 minutes",
                type: "Text",
                data: {
                  text: "23 hours and 49 minutes",
                },
              },
              {
                term: "hour(s)",
                type: "Text",
                data: {
                  text: "hour(s)",
                },
              },
            ],
          ],
          filters: [
            {
              filter: "table",
              filterName: "keyword",
              type: "keyword",
              value: "",
              keys: ["ip", "ban_start", "ban_end"],
              field: {
                id: "bans-keyword",
                value: "",
                type: "text",
                name: "bans-keyword",
                label: "bans_search",
                placeholder: "inp_keyword",
                isClipboard: false,
                popovers: [
                  {
                    text: "bans_search_desc",
                    iconName: "info",
                  },
                ],
                columns: {
                  pc: 3,
                  tablet: 4,
                  mobile: 12,
                },
              },
            },
            {
              filter: "table",
              filterName: "reason",
              type: "select",
              value: "all",
              keys: ["reason"],
              field: {
                id: "bans-reason",
                value: "all",
                values: ["all", "ui", "cor"],
                name: "bans-reason",
                onlyDown: true,
                label: "bans_reason",
                popovers: [
                  {
                    text: "bans_reason_desc",
                    iconName: "info",
                  },
                ],
                columns: {
                  pc: 3,
                  tablet: 4,
                  mobile: 12,
                },
              },
            },
            {
              filter: "table",
              filterName: "term",
              type: "select",
              value: "all",
              keys: ["term"],
              field: {
                id: "bans-terms",
                value: "all",
                values: ["all", "hour(s)", "day(s)"],
                name: "bans-terms",
                onlyDown: true,
                label: "bans_terms",
                popovers: [
                  {
                    text: "bans_terms_desc",
                    iconName: "info",
                  },
                ],
                columns: {
                  pc: 3,
                  tablet: 4,
                  mobile: 12,
                },
              },
            },
          ],
        },
      },
    ],
  },
];
</script>

<template>
  <DashboardLayout>
    <BuilderBans v-if="builder" :builder="builder" />
  </DashboardLayout>
</template>
