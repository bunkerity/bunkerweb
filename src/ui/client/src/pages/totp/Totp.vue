<script setup>
import Loader from "@components/Loader.vue";
import LangSwitch from "@components/LangSwitch.vue";
import LogoutInpGroup from "@components/Logout/InpGroup.vue";
import LogoutInput from "@components/Logout/Input.vue";
import FeedbackAlert from "@components/Feedback/Alert.vue";
import { onMounted, reactive } from "vue";

const data = reactive({
  isErr: false,
});

function showErr() {
  data.isErr = true;
  setTimeout(() => {
    data.isErr = false;
  }, 5000);
}

onMounted(() => {
  const query = window.location.search;
  if (query.includes("error=True")) showErr();
  tsParticles.load("particles-js", {
    background: {
      position: "82% 50%",
      repeat: "no-repeat",
      size: "20%",
    },
    fullScreen: {
      enabled: true,
      zIndex: -1,
    },
    fpsLimit: 120,
    particles: {
      color: {
        value: "#40bb6b",
      },
      links: {
        color: {
          value: "#ffffff",
        },
        enable: true,
        opacity: 0.4,
      },
      move: {
        enable: true,
        path: {},
        outModes: {
          bottom: "out",
          left: "out",
          right: "out",
          top: "out",
        },
        speed: 4,
        spin: {},
      },
      number: {
        density: {
          enable: true,
        },
        value: 80,
      },
      opacity: {
        value: 0.5,
        animation: {},
      },
      size: {
        value: {
          min: 0.1,
          max: 3,
        },
        animation: {},
      },
      zIndex: {
        value: -1,
      },
    },
  });
});
</script>

<template>
  <Loader />
  <LangSwitch />
  <div class="logout-alert-container">
    <FeedbackAlert
      @close="data.isErr = false"
      id="logout-error"
      type="error"
      status="403"
      :message="$t('totp_error')"
      v-if="data.isErr"
    />
  </div>
  <main class="totp-main">
    <!--form -->
    <div class="totp-container">
      <div class="totp-logo-container">
        <div class="flex justify-center">
          <img
            class="max-w-60 max-h-30 mb-6"
            src="/images/BUNKERWEB-print-hd.png"
            :alt="$t('totp_logo_alt')"
          />
        </div>
        <h1 class="totp-title">
          {{ $t("totp_title") }}
        </h1>
        <form @submit.prevent action="/login" method="POST" autocomplete="off">
          <LogoutInpGroup>
            <LogoutInput
              :label="$t('totp_code')"
              name="totp-code"
              pattern="(.*?)"
              :placeholder="$t('totp_code_placeholder')"
              type="text"
              :required="true"
            />
          </LogoutInpGroup>

          <div class="flex justify-center">
            <button type="submit" id="totp" class="logout-submit-btn">
              {{ $t("totp_button") }}
            </button>
          </div>
        </form>
      </div>
    </div>
    <!-- end form -->
    <!-- particles -->
    <div class="totp-particle-container">
      <div id="particles-js" class="totp-img [&>*]:bg-primary"></div>
    </div>
  </main>
</template>
