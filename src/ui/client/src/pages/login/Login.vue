<script setup>
import Loader from "@components/Loader.vue";
import LangSwitch from "@components/LangSwitch.vue";
import AccountInpGroup from "@components/Account/InpGroup.vue";
import AccountInput from "@components/Account/Input.vue";
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
  <div class="account-alert-container">
    <FeedbackAlert
      @close="data.isErr = false"
      id="account-error"
      type="error"
      status="403"
      message="Wrong username or password"
      v-if="data.isErr"
    />
  </div>
  <main class="login-main">
    <!--form -->
    <div class="login-container">
      <div class="login-logo-container">
        <div class="flex justify-center">
          <img
            class="lg:hidden max-w-60 max-h-30 mb-6"
            src="/images/BUNKERWEB-print-hd.png"
            alt="logo"
          />
        </div>
        <h1 class="login-title-desktop">
          {{ $t("login_title") }}
        </h1>
        <form action="/login" method="POST" autocomplete="off">
          <!-- username inpt-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('login_username')"
              name="username"
              pattern="(.*?)"
              :placeholder="$t('login_username_placeholder')"
              type="text"
              :required="true"
            />
          </AccountInpGroup>
          <!-- end username inpt-->
          <!-- password inpt-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('login_password')"
              name="password"
              pattern="(.*?)"
              :placeholder="$t('login_password_placeholder')"
              type="password"
              :required="true"
            />
          </AccountInpGroup>
          <!-- end password inpt-->
          <div class="flex justify-center">
            <button
              type="submit"
              id="login"
              name="login"
              value="login"
              class="account-submit-btn"
            >
              {{ $t("login_log_button") }}
            </button>
          </div>
        </form>
      </div>
    </div>
    <!-- end form -->
    <!-- particles -->
    <div class="login-particle-container">
      <div id="particles-js" class="login-img [&>*]:bg-primary"></div>
      <div class="hidden lg:flex justify-center">
        <img
          class="max-w-60 max-h-30"
          src="/images/BUNKERWEB-print-hd-blanc.png"
          :alt="$t('login_logo_alt')"
        />
      </div>
    </div>
  </main>
</template>
