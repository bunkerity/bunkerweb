<script setup>
import Loader from "@components/Loader.vue";
import LangSwitch from "@components/LangSwitch.vue";
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
  if (query.includes("errpr=True")) showErr();
  tsParticles.loadJSON("particles-js", "/json/particles.json");
});
</script>

<template>
  <Loader />
  <LangSwitch />
  <div class="login-alert-container">
    <FeedbackAlert
      @close="data.isErr = false"
      id="login-error"
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
          {{ $t("title") }}
        </h1>
        <form action="/login" method="POST" autocomplete="off">
          <!-- username inpt-->
          <div class="login-input-group">
            <label for="username" class="login-label">
              {{ $t("username") }}
            </label>
            <input
              type="username"
              id="username"
              name="username"
              class="login-input"
              :placeholder="$t('username_placeholder')"
              pattern="(.*?)"
              required
            />
          </div>
          <!-- end username inpt-->
          <!-- password inpt-->
          <div class="login-input-group">
            <label for="password" class="login-label">
              {{ $t("password") }}
            </label>
            <input
              type="password"
              id="password"
              name="password"
              class="login-input"
              :placeholder="$t('password_placeholder')"
              pattern="(.*?)"
              required
            />
          </div>
          <!-- end password inpt-->
          <div class="flex justify-center">
            <button
              type="submit"
              id="login"
              name="login"
              value="login"
              class="login-submit-btn"
            >
              {{ $t("log_button") }}
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
          alt="logo"
        />
      </div>
    </div>
  </main>
</template>
