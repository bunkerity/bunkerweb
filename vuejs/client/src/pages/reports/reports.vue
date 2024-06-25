<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import BuilderReports from "@components/Builder/Reports.vue";
import { useGlobal } from "@utils/global.js";
import { useForm } from "@utils/form.js";

/**
  @name Page/Reports.vue
  @description This component is the report page.
  This page displays global information about reports, and allow to delete or upload some reports.
*/

const reports = reactive({
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
  reports.builder = data;
});

onMounted(() => {
  useGlobal();
  useForm();
});

const builder = [
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
          title: "reports_title",
        },
      },
      {
        type: "Table",
        data: {
          title: "reports_table_title",
          minWidth: "lg",
          header: [
            "reports_table_date",
            "reports_table_ip",
            "reports_table_country",
            "reports_table_method",
            "reports_table_url",
            "reports_table_status_code",
            "reports_table_cache_user_agent",
            "reports_table_reason",
            "reports_table_data",
          ],
          positions: [1, 1, 1, 1, 2, 1, 2, 1, 2],
          items: [
            [
              {
                date: "25/06/2024 07:40:23",
                type: "Text",
                data: {
                  text: "25/06/2024 07:40:23",
                },
              },
              {
                ip: "172.21.0.1",
                type: "Text",
                data: {
                  text: "172.21.0.1",
                },
              },
              {
                country: "local",
                type: "Text",
                data: {
                  text: "local",
                },
              },
              {
                method: "GET",
                type: "Text",
                data: {
                  text: "GET",
                },
              },
              {
                url: "/admin/login?id=etc/passwd",
                type: "Text",
                data: {
                  text: "/admin/login?id=etc/passwd",
                },
              },
              {
                code: "403",
                type: "Text",
                data: {
                  text: "403",
                },
              },
              {
                user_agent:
                  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                type: "Text",
                data: {
                  text: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                },
              },
              {
                reason: "modsecurity",
                type: "Text",
                data: {
                  text: "modsecurity",
                },
              },
              {
                data: {
                  text: '{"fesfesfsefesfesfesfesfesfesfesfesfesfsefes": "fesfs"}',
                },
                type: "Text",
              },
            ],
            [
              {
                date: "25/06/2024 07:40:23",
                type: "Text",
                data: {
                  text: "25/06/2024 07:40:23",
                },
              },
              {
                ip: "111111",
                type: "Text",
                data: {
                  text: "111111",
                },
              },
              {
                country: "fr",
                type: "Text",
                data: {
                  text: "fr",
                },
              },
              {
                method: "POST",
                type: "Text",
                data: {
                  text: "POST",
                },
              },
              {
                url: "/admin/login?id=e",
                type: "Text",
                data: {
                  text: "/admin/login?id=e",
                },
              },
              {
                code: "403",
                type: "Text",
                data: {
                  text: "403",
                },
              },
              {
                user_agent:
                  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                type: "Text",
                data: {
                  text: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                },
              },
              {
                reason: " antibot",
                type: "Text",
                data: {
                  text: " antibot",
                },
              },
              {
                data: {
                  text: "{}",
                },
                type: "Text",
              },
            ],
            [
              {
                date: "25/06/2024 07:40:23",
                type: "Text",
                data: {
                  text: "25/06/2024 07:40:23",
                },
              },
              {
                ip: "111111",
                type: "Text",
                data: {
                  text: "111111",
                },
              },
              {
                country: "fr",
                type: "Text",
                data: {
                  text: "fr",
                },
              },
              {
                method: "POST",
                type: "Text",
                data: {
                  text: "POST",
                },
              },
              {
                url: "/admin/login?id=e",
                type: "Text",
                data: {
                  text: "/admin/login?id=e",
                },
              },
              {
                code: "403",
                type: "Text",
                data: {
                  text: "403",
                },
              },
              {
                user_agent:
                  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                type: "Text",
                data: {
                  text: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                },
              },
              {
                reason: " antibot",
                type: "Text",
                data: {
                  text: " antibot",
                },
              },
              {
                data: {
                  text: "{}",
                },
                type: "Text",
              },
            ],
            [
              {
                date: "25/06/2024 07:40:23",
                type: "Text",
                data: {
                  text: "25/06/2024 07:40:23",
                },
              },
              {
                ip: "111111",
                type: "Text",
                data: {
                  text: "111111",
                },
              },
              {
                country: "fr",
                type: "Text",
                data: {
                  text: "fr",
                },
              },
              {
                method: "POST",
                type: "Text",
                data: {
                  text: "POST",
                },
              },
              {
                url: "/admin/login?id=e",
                type: "Text",
                data: {
                  text: "/admin/login?id=e",
                },
              },
              {
                code: "403",
                type: "Text",
                data: {
                  text: "403",
                },
              },
              {
                user_agent:
                  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                type: "Text",
                data: {
                  text: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                },
              },
              {
                reason: " antibot",
                type: "Text",
                data: {
                  text: " antibot",
                },
              },
              {
                data: {
                  text: "{}",
                },
                type: "Text",
              },
            ],
            [
              {
                date: "25/06/2024 07:40:23",
                type: "Text",
                data: {
                  text: "25/06/2024 07:40:23",
                },
              },
              {
                ip: "111111",
                type: "Text",
                data: {
                  text: "111111",
                },
              },
              {
                country: "fr",
                type: "Text",
                data: {
                  text: "fr",
                },
              },
              {
                method: "POST",
                type: "Text",
                data: {
                  text: "POST",
                },
              },
              {
                url: "/admin/login?id=e",
                type: "Text",
                data: {
                  text: "/admin/login?id=e",
                },
              },
              {
                code: "403",
                type: "Text",
                data: {
                  text: "403",
                },
              },
              {
                user_agent:
                  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                type: "Text",
                data: {
                  text: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                },
              },
              {
                reason: " antibot",
                type: "Text",
                data: {
                  text: " antibot",
                },
              },
              {
                data: {
                  text: "{}",
                },
                type: "Text",
              },
            ],
          ],
          filters: [],
        },
      },
    ],
  },
];
</script>

<template>
  <DashboardLayout>
    <BuilderReports v-if="builder" :builder="builder" />
  </DashboardLayout>
</template>
