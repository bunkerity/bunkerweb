<script setup>
import { reactive, onBeforeMount, triggerRef } from "vue";
import Input from "@components/Forms/Field/Input.vue";
import Combobox from "@components/Forms/Field/Combobox.vue";
import Editor from "@components/Forms/Field/Editor.vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Grid from "@components/Widget/Grid.vue";
import Table from "@components/Widget/Table.vue";

const inputData = {
  id: "test-input",
  value: "yes",
  type: "password",
  name: "test-input",
  disabled: false,
  required: true,
  label: "Test input",
  pattern: "(test)",
  columns: { pc: 12, tablet: 12, mobile: 12 },
};

const comboboxData = {
  id: "test-combobox",
  value: "yes",
  values: ["yes", "no", "tes", "f", "fes", "esd", "fesfse"],
  name: "test-combobox",
  disabled: false,
  required: false,
  requiredValues: ["no"],
  label: "Test combobox",
  columns: { pc: 12, tablet: 12, mobile: 12 },
};

const editorData = {
  id: "test-editor",
  value: "yes",
  name: "test-editor",
  disabled: false,
  required: true,
  pattern: "(test)",
  label: "Test editor",
  tabId: "1",
  columns: { pc: 12, tablet: 12, mobile: 12 },
};

const tableData = {
  title: "Table title",
  minWidth: "lg",
  header: [
    "Name",
    "Type",
    "Interval",
    "Last run",
    "Success",
    "Last run time",
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
