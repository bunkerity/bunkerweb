<script setup>
import Loader from "@components/Loader.vue";
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
  <div class="fixed bottom-4 right-0 min-w-[340px]">
    <FeedbackAlert
      @close="data.isErr = false"
      id="login-error"
      type="error"
      status="403"
      message="Wrong username or password"
      v-if="data.isErr"
    />
  </div>
  <main class="grid grid-cols-2 align-middle items-center min-h-screen">
    <!--form -->
    <div
      class="mx-4 lg:mx-0 col-span-2 lg:col-span-1 bg-none lg:bg-gray-50 h-full flex flex-col items-center justify-center"
    >
      <div class="bg-gray-50 rounded px-12 py-16 w-full max-w-[400px]">
        <div class="flex justify-center">
          <img
            class="lg:hidden max-w-60 max-h-30 mb-6"
            src="/images/BUNKERWEB-print-hd.png"
            alt="logo"
          />
        </div>
        <h1 class="hidden lg:block text-center font-bold dark:text-white mb-8">
          Log in
        </h1>
        <form action="/login" method="POST" autocomplete="off">
          <!-- username inpt-->
          <div class="flex flex-col relative col-span-12 my-3">
            <h5
              class="my-1 transition duration-300 ease-in-out dark:opacity-90 text-md font-bold m-0 dark:text-gray-300"
            >
              Username
            </h5>
            <input
              type="username"
              id="username"
              name="username"
              class="col-span-12 dark:border-slate-600 dark:bg-slate-700 dark:text-gray-300 disabled:opacity-75 focus:valid:border-green-500 focus:invalid:border-red-500 outline-none focus:border-primary text-sm leading-5.6 ease block w-full appearance-none rounded-lg border border-solid border-gray-300 bg-white bg-clip-padding px-4 py-2 font-normal text-gray-700 transition-all placeholder:text-gray-500"
              placeholder="enter username"
              pattern="(.*?)"
              required
            />
          </div>
          <!-- end username inpt-->
          <!-- password inpt-->
          <div class="flex flex-col relative col-span-12 my-3">
            <h5
              class="my-1 transition duration-300 ease-in-out dark:opacity-90 text-md font-bold m-0 dark:text-gray-300"
            >
              Password
            </h5>
            <input
              type="password"
              id="password"
              name="password"
              class="col-span-12 dark:border-slate-600 dark:bg-slate-700 dark:text-gray-300 disabled:opacity-75 focus:valid:border-green-500 focus:invalid:border-red-500 outline-none focus:border-primary text-sm leading-5.6 ease block w-full appearance-none rounded-lg border border-solid border-gray-300 bg-white bg-clip-padding px-4 py-2 font-normal text-gray-700 transition-all placeholder:text-gray-500"
              placeholder="enter password"
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
              class="my-4 dark:brightness-90 inline-block px-6 py-3 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer bg-primary hover:bg-primary/80 focus:bg-primary/80 leading-normal text-sm ease-in tracking-tight-rem shadow-xs bg-150 bg-x-25 hover:-translate-y-px active:opacity-85 hover:shadow-md"
            >
              Log in
            </button>
          </div>
        </form>
      </div>
    </div>
    <!-- end form -->
    <!-- particles -->
    <div class="-z-10 fixed lg:relative lg:col-span-1 bg-primary">
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
