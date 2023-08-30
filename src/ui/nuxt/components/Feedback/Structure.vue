<script setup>
const dropdown = reactive({
  isOpen: false,
});

const feedback = useFeedbackStore();
const showDelay = 4000;
const alert = reactive({
  show: true,
  prevNum: 0,
});

onMounted(() => {
  setTimeout(() => {
    alert.show = false;
  }, showDelay);
});

watch(feedback, () => {
  if (alert.prevNum < feedback.data.length) {
    alert.prevNum = feedback.data.length;
    alert.show = true;

    setTimeout(() => {
      alert.show = false;
    }, showDelay);
  }

  if (alert.prevNum > feedback.data.length)
    alert.prevNum = feedback.data.length;
});
</script>

<template>
  <!-- float button-->
  <div
    class="group group-hover hover:brightness-75 dark:hover:brightness-105 fixed top-2 sm:top-3 right-20 sm:right-24 xl:right-24 z-990"
  >
    <button
      @click="dropdown.isOpen = dropdown.isOpen ? false : true"
      class="transition scale-90 sm:scale-100 dark:brightness-95 p-3 text-xl bg-white shadow-sm cursor-pointer rounded-circle text-slate-700"
    >
      <svg
        class="pointer-events-none fill-yellow-500 -translate-y-0.4 h-6 w-6"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 448 512"
      >
        <path
          d="M224 0c-17.7 0-32 14.3-32 32V51.2C119 66 64 130.6 64 208v18.8c0 47-17.3 92.4-48.5 127.6l-7.4 8.3c-8.4 9.4-10.4 22.9-5.3 34.4S19.4 416 32 416H416c12.6 0 24-7.4 29.2-18.9s3.1-25-5.3-34.4l-7.4-8.3C401.3 319.2 384 273.9 384 226.8V208c0-77.4-55-142-128-156.8V32c0-17.7-14.3-32-32-32zm45.3 493.3c12-12 18.7-28.3 18.7-45.3H224 160c0 17 6.7 33.3 18.7 45.3s28.3 18.7 45.3 18.7s33.3-6.7 45.3-18.7z"
        />
      </svg>
    </button>
    <div
      class="pointer-events-none dark:brightness-95 px-2 translate-x-2 bottom-0 right-0 absolute rounded-full bg-white"
    >
      <p class="mb-0 text-sm text-bold text-red-500">
        {{ feedback.data.length }}
      </p>
    </div>
  </div>
  <!-- end float button-->

  <div
    class="flex justify-center fixed right-0 bottom-0 w-full sm:max-w-[300px] z-[1000]"
  >
    <FeedbackAlert
      v-if="alert.show"
      :type="feedback.data[feedback.data.length - 1].type"
      :id="feedback.data[feedback.data.length - 1].id"
      :status="feedback.data[feedback.data.length - 1].status"
      :message="feedback.data[feedback.data.length - 1].message"
      @close="alert.show = false"
    />
  </div>

  <!-- right sidebar -->
  <aside
    :class="[dropdown.isOpen ? '' : 'translate-x-90']"
    class="-right-0 transition z-sticky dark:bg-slate-850 dark:brightness-110 shadow-3xl max-w-full w-90 ease fixed top-0 left-auto flex h-full min-w-0 flex-col break-words rounded-none border-0 bg-white bg-clip-border px-0.5"
  >
    <!-- close btn-->
    <button
      class="absolute h-5 w-5 top-4 right-4"
      @click="dropdown.isOpen = false"
    >
      <svg
        class="cursor-pointer fill-gray-600 dark:fill-gray-300 dark:opacity-80"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 320 512"
      >
        <path
          d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
        />
      </svg>
    </button>

    <!-- close btn-->

    <!-- header -->
    <div class="px-6 pt-4 pb-0 mb-0 border-b-0 rounded-t-2xl">
      <div class="float-left">
        <h5 class="mt-4 mb-1 dark:text-white font-bold">MESSAGES</h5>
        <p class="dark:text-white dark:opacity-80 mb-0">Feedback actions</p>
      </div>
      <!-- close button -->
      <div class="float-right mt-6">
        <button
          data-flash-sidebar-close
          class="inline-block p-0 mb-4 text-sm font-bold leading-normal text-center uppercase align-middle transition-all ease-in bg-transparent border-0 rounded-lg shadow-none cursor-pointer hover:-translate-y-px tracking-tight-rem bg-150 bg-x-25 active:opacity-85 dark:text-white text-slate-700"
        >
          <i class="fa fa-close"></i>
        </button>
      </div>
      <!-- end close button -->
    </div>
    <!-- end header -->

    <!-- messages-->
    <div
      class="flex flex-col justify-start items-center h-full m-2 overflow-y-auto"
    >
      <!-- flash message-->
      <FeedbackAlert
        v-for="(item, id) in feedback.data"
        :type="item.type"
        :id="item.id"
        :status="item.status"
        :message="item.message"
        @close="feedback.removeFeedback(item.id)"
      />

      <!-- end flash message-->
    </div>
    <!-- end messages -->
  </aside>
  <!-- end right sidebar -->
</template>
