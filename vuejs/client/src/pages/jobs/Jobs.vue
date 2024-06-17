<script setup>
import { reactive, onBeforeMount, onMounted } from "vue";
import { useGlobal } from "@utils/global.js";
import { useForm } from "@utils/form.js";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Grid from "@components/Widget/Grid.vue";
import Table from "@components/Widget/Table.vue";
/**
  @name Page/Jobs.vue
  @description This component is the jobs page.
  This page displays some useful information about the jobs.
*/

const services = reactive({
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
  services.builder = data;
});

onMounted(() => {
  useGlobal();
  useForm();
});

// const builder = [
//   {
//     type: "card",
//     containerColumns: { pc: 12, tablet: 12, mobile: 12 },
//     widgets: [
//       {
//         type: "Table",
//         data: {
//           title: "jobs_title",
//           subtitleColor: "success" is is_pro_version else "warning",
//           stat: "home_pro" if is_pro_version else "home_free",
//           iconName: "crown" if is_pro_version else "core",
//           iconColor: "amber",
//         },
//       },
//     ],
//   },
const tableData = {
  title: "Table title",
  minWidth: "lg",
  header: [
    "Name",
    "Type",
    "Interval",
    "Last run",
    "Success",
    "last run date",
    "Cache",
  ],
  positions: [2, 2, 1, 1, 1, 3, 2],
  items: [
    [
      {
        type: "Text",
        data: {
          text: "anonymous-report",
        },
      },
      {
        type: "Text",
        data: {
          text: "misc",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "error",
          iconName: "cross",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:11 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "backup-data",
        },
      },
      {
        type: "Text",
        data: {
          text: "backup",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "error",
          iconName: "cross",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:10 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "blacklist-download",
        },
      },
      {
        type: "Text",
        data: {
          text: "blacklist",
        },
      },
      {
        type: "Text",
        data: {
          text: "hour",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:09 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "bunkernet-data",
        },
      },
      {
        type: "Text",
        data: {
          text: "bunkernet",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:11 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "bunkernet-register",
        },
      },
      {
        type: "Text",
        data: {
          text: "bunkernet",
        },
      },
      {
        type: "Text",
        data: {
          text: "hour",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:09 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "certbot-new",
        },
      },
      {
        type: "Text",
        data: {
          text: "letsencrypt",
        },
      },
      {
        type: "Text",
        data: {
          text: "once",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "error",
          iconName: "cross",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:08 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "certbot-renew",
        },
      },
      {
        type: "Text",
        data: {
          text: "letsencrypt",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:09 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "coreruleset-nightly",
        },
      },
      {
        type: "Text",
        data: {
          text: "modsecurity",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:09 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "custom-cert",
        },
      },
      {
        type: "Text",
        data: {
          text: "customcert",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:10 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "default-server-cert",
        },
      },
      {
        type: "Text",
        data: {
          text: "misc",
        },
      },
      {
        type: "Text",
        data: {
          text: "once",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "error",
          iconName: "cross",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:10 PM",
        },
      },
      {
        type: "Fields",
        data: {
          setting: {
            id: "default-server-cert_cache",
            label: "default-server-cert_cache",
            hideLabel: true,
            inpType: "select",
            name: "default-server-cert_cache",
            value: "none",
            values: [
              "none",
              "default-server-cert.pem",
              "default-server-cert.key",
            ],
            columns: {
              pc: 12,
              tablet: 12,
              mobile: 12,
            },
            overflowAttrEl: "data-table-body",
            containerClass: "table",
            maxBtnChars: 16,
            popovers: [
              {
                iconColor: "info",
                iconName: "info",
                text: "jobs_download_cache_file",
              },
            ],
          },
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "download-plugins",
        },
      },
      {
        type: "Text",
        data: {
          text: "misc",
        },
      },
      {
        type: "Text",
        data: {
          text: "once",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "error",
          iconName: "cross",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:13 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "download-pro-plugins",
        },
      },
      {
        type: "Text",
        data: {
          text: "pro",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:10 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "failover-backup",
        },
      },
      {
        type: "Text",
        data: {
          text: "jobs",
        },
      },
      {
        type: "Text",
        data: {
          text: "once",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "error",
          iconName: "cross",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:16 PM",
        },
      },
      {
        type: "Fields",
        data: {
          setting: {
            id: "failover-backup_cache",
            label: "failover-backup_cache",
            hideLabel: true,
            inpType: "select",
            name: "failover-backup_cache",
            value: "none",
            values: ["none", "folder:/var/tmp/bunkerweb/failover.tgz"],
            columns: {
              pc: 12,
              tablet: 12,
              mobile: 12,
            },
            overflowAttrEl: "data-table-body",
            containerClass: "table",
            maxBtnChars: 16,
            popovers: [
              {
                iconColor: "info",
                iconName: "info",
                text: "jobs_download_cache_file",
              },
            ],
          },
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "greylist-download",
        },
      },
      {
        type: "Text",
        data: {
          text: "greylist",
        },
      },
      {
        type: "Text",
        data: {
          text: "hour",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:09 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "mmdb-asn",
        },
      },
      {
        type: "Text",
        data: {
          text: "jobs",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:14 PM",
        },
      },
      {
        type: "Fields",
        data: {
          setting: {
            id: "mmdb-asn_cache",
            label: "mmdb-asn_cache",
            hideLabel: true,
            inpType: "select",
            name: "mmdb-asn_cache",
            value: "none",
            values: ["none", "asn.mmdb"],
            columns: {
              pc: 12,
              tablet: 12,
              mobile: 12,
            },
            overflowAttrEl: "data-table-body",
            containerClass: "table",
            maxBtnChars: 16,
            popovers: [
              {
                iconColor: "info",
                iconName: "info",
                text: "jobs_download_cache_file",
              },
            ],
          },
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "mmdb-country",
        },
      },
      {
        type: "Text",
        data: {
          text: "jobs",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:12 PM",
        },
      },
      {
        type: "Fields",
        data: {
          setting: {
            id: "mmdb-country_cache",
            label: "mmdb-country_cache",
            hideLabel: true,
            inpType: "select",
            name: "mmdb-country_cache",
            value: "none",
            values: ["none", "country.mmdb"],
            columns: {
              pc: 12,
              tablet: 12,
              mobile: 12,
            },
            overflowAttrEl: "data-table-body",
            containerClass: "table",
            maxBtnChars: 16,
            popovers: [
              {
                iconColor: "info",
                iconName: "info",
                text: "jobs_download_cache_file",
              },
            ],
          },
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "realip-download",
        },
      },
      {
        type: "Text",
        data: {
          text: "realip",
        },
      },
      {
        type: "Text",
        data: {
          text: "hour",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:09 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "self-signed",
        },
      },
      {
        type: "Text",
        data: {
          text: "selfsigned",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:10 PM",
        },
      },
      {
        type: "Fields",
        data: {
          setting: {
            id: "self-signed_cache",
            label: "self-signed_cache",
            hideLabel: true,
            inpType: "select",
            name: "self-signed_cache",
            value: "none",
            values: [
              "none",
              "www.example.com/cert.pem",
              "www.example.com/key.pem",
            ],
            columns: {
              pc: 12,
              tablet: 12,
              mobile: 12,
            },
            overflowAttrEl: "data-table-body",
            containerClass: "table",
            maxBtnChars: 16,
            popovers: [
              {
                iconColor: "info",
                iconName: "info",
                text: "jobs_download_cache_file",
              },
            ],
          },
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "update-check",
        },
      },
      {
        type: "Text",
        data: {
          text: "jobs",
        },
      },
      {
        type: "Text",
        data: {
          text: "day",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "error",
          iconName: "cross",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:15 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
    [
      {
        type: "Text",
        data: {
          text: "whitelist-download",
        },
      },
      {
        type: "Text",
        data: {
          text: "whitelist",
        },
      },
      {
        type: "Text",
        data: {
          text: "hour",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Icons",
        data: {
          iconColor: "success",
          iconName: "check",
        },
      },
      {
        type: "Text",
        data: {
          text: "2024/06/14, 01:33:09 PM",
        },
      },
      {
        type: "Text",
        data: {
          text: "No cache",
        },
      },
    ],
  ],
};
</script>

<template>
  <DashboardLayout>
    <GridLayout :columns="{ pc: 12, tablet: 12, mobile: 12 }">
      <!-- widget grid -->
      <Grid>
        <Table v-bind="tableData" />
      </Grid>
    </GridLayout>
  </DashboardLayout>
</template>
