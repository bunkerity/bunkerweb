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

// TO UPDATE

class ServerCheck {
  constructor() {
    this.servInp = document.querySelector("#server_name");
    this.checkBtn = document.querySelector("#check-server-name");
    this.checkRes = document.querySelector("[aria-check-result]");
    this.checkColor = document.querySelector("[aria-check-color]");
    this.sslCheck = document.querySelector("#auto_lets_encrypt");
    this.init();
  }

  init() {
    // Set check as unkwnown when new server name
    this.servInp.addEventListener("input", () => {
      this.updateCheck("unknown", "bg-gray-300");
    });

    // Check for endpoint on button fetch
    this.checkBtn.addEventListener("click", (e) => {
      e.preventDefault();
      this.updateCheck("unknown");
      // get resume
      const api = `http${
        this.sslCheck.getAttribute("aria-checked") === "true" ? "s" : ""
      }://${this.servInp.value}/setup/check`;
      fetch(api)
        .then((res) => {
          this.updateCheck("success");
        })
        .catch((err) => {
          this.updateCheck("error");
        });
    });
  }

  // state can be success, error or unknown
  updateCheck(state) {
    this.removeCheckStyle();

    if (state === "success") {
      return this.setCheck("success", "bg-green-500");
    }

    if (state === "error") {
      return this.setCheck("error", "bg-red-500");
    }

    return this.setCheck("unknown", "bg-gray-300");
  }

  setCheck(state, bgColor) {
    this.checkColor.classList.add(bgColor);
    this.checkRes.textContent = state;
  }

  removeCheckStyle() {
    this.checkColor.classList.remove(
      "bg-gray-300",
      "bg-green-500",
      "bg-red-500"
    );
    this.checkRes.textContent = "";
  }
}

class Resume {
  constructor() {
    this.servInp = document.querySelector("#server_name");
    this.sslCheck = document.querySelector("#auto_lets_encrypt");
    this.urlInp = document.querySelector("#ui_url");
    this.resumeEl = document.querySelector("[data-resume]");
    this.init();
  }

  init() {
    // Show default resume
    this.updateResume();
    // Update with handlers
    const listenInps = [this.servInp, this.urlInp];
    listenInps.forEach((inp) => {
      inp.addEventListener("input", (e) => {
        this.updateResume();
      });
    });

    this.sslCheck.addEventListener("change", (e) => {
      this.updateResume();
    });
  }

  updateResume() {
    this.resumeEl.textContent = `http${
      this.sslCheck.getAttribute("aria-checked") === "true" ? "s" : ""
    }://${this.servInp.value}${this.urlInp.value}`;
  }
}

class Loader {
  constructor() {
    this.menuContainer = document.querySelector("[data-menu-container]");
    this.loaderContainer = document.querySelector("[data-loader]");
    this.logoEl = document.querySelector("[data-loader-img]");
    this.isLoading = true;
    this.init();
  }

  init() {
    this.loaderContainer.setAttribute("aria-hidden", "false");
    this.loading();
    window.addEventListener("load", (e) => {
      setTimeout(() => {
        this.loaderContainer.classList.add("opacity-0");
      }, 550);

      setTimeout(() => {
        this.isLoading = false;
        this.loaderContainer.classList.add("hidden");
        this.loaderContainer.setAttribute("aria-hidden", "true");
      }, 850);
    });
  }

  loading() {
    if ((this.isLoading = true)) {
      setTimeout(() => {
        this.logoEl.classList.toggle("scale-105");
        this.loading();
      }, 300);
    }
  }
}

class Checkbox {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      //prevent default checkbox behavior
      try {
        //case a related checkbox element is clicked and checkbox is enabled
        if (
          e.target.closest("div").hasAttribute("data-checkbox-handler") &&
          !e.target
            .closest("div")
            .querySelector('input[type="checkbox"]')
            .hasAttribute("disabled")
        ) {
          //get related checkbox
          const checkboxEl = e.target
            .closest("div")
            .querySelector('input[type="checkbox"]');

          const prevValue = checkboxEl.getAttribute("value");

          //set attribute value for new state
          prevValue === "no"
            ? checkboxEl.setAttribute("value", "yes")
            : checkboxEl.setAttribute("value", "no");

          //set custom input hidden value
          const newValue = checkboxEl.getAttribute("value");
          newValue === "yes"
            ? checkboxEl.setAttribute("aria-checked", "true")
            : checkboxEl.setAttribute("aria-checked", "false");

          //force checked for submit
          checkboxEl.checked = true;
        }
      } catch (err) {}
    });
  }
}

class SubmitForm {
  constructor() {
    this.pwEl = document.querySelector("#admin_password");
    this.pwCheckEl = document.querySelector("#admin_password_check");
    this.pwAlertEl = document.querySelector("[data-pw-alert]");
    this.formEl = document.querySelector("#setup-form");
    this.servInp = document.querySelector("#server_name");
    this.sslCheck = document.querySelector("#auto_lets_encrypt");
    this.urlInp = document.querySelector("#ui_url");
    this.loaderContainer = document.querySelector("[data-loader]");
    this.logoEl = document.querySelector("[data-loader-img]");
    this.loaderMsg = document.querySelector("[data-loader-msg]");
    this.isLoading = false;
    this.flashMsg = document.querySelector("[data-flash-message]");
    this.init();
  }

  init() {
    // Check password to send
    this.checkSamePW();
    this.pwCheckEl.addEventListener("input", (e) => {
      this.checkSamePW();
    });

    this.pwEl.addEventListener("input", (e) => {
      this.checkSamePW();
    });

    // Case error and display msg
    window.addEventListener("click", (e) => {
      try {
        if (
          e.target.closest("button").hasAttribute("data-close-flash-message")
        ) {
          this.hideErrMsg();
        }
      } catch (err) {}
    });

    // Submit
    this.formEl.addEventListener("submit", (e) => {
      // Case not same PW
      if (this.pwEl.value !== this.pwCheckEl.value) return e.preventDefault();

      e.preventDefault();

      // Show loader
      this.showLoader();
      this.hideErrMsg();
      // Else, send form and wait for response

      const api = `http${
        this.sslCheck.getAttribute("aria-checked") === "true" ? "s" : ""
      }://${this.servInp.value}${this.urlInp.value}`;

      fetch(window.location.href, {
        method: "POST",
        body: new FormData(this.formEl),
      })
        .then((res) => {
          if (res.status === 200) {
            setTimeout(() => {
              window.open(`${api}/login`, "_self");
            }, 60000);
            setInterval(() => {
              fetch(`${api}/check`, {
                cache: "no-cache",
              })
                .then((res) => {
                  if (res.status === 200) {
                    window.open(`${api}/login`, "_self");
                  }
                })
                .catch((err) => {});
            }, 5000);
          }
        })
        .catch((err) => {
          setTimeout(() => {
            this.stopLoader();
            this.showErrMsg();
          }, 400);
        });
    });
  }

  checkSamePW() {
    if (!this.pwEl.value || !this.pwCheckEl.value) return this.hidePWAlert();

    if (this.pwEl.value !== this.pwCheckEl.value) return this.showPWAlert();

    return this.hidePWAlert();
  }

  showErrMsg() {
    this.flashMsg.classList.remove("hidden");
    this.flashMsg.setAttribute("aria-hidden", "false");
  }

  hideErrMsg() {
    this.flashMsg.classList.add("hidden");
    this.flashMsg.setAttribute("aria-hidden", "true");
  }

  hidePWAlert() {
    this.pwCheckEl.classList.remove(
      "focus:!border-red-500",
      "focus:valid:!border-red-500",
      "active:!border-red-500",
      "active:valid:!border-red-500",
      "valid:!border-red-500"
    );
    this.pwAlertEl.classList.add("opacity-0");
    this.pwAlertEl.setAttribute("aria-hidden", "true");
  }

  showPWAlert() {
    this.pwCheckEl.classList.add(
      "focus:!border-red-500",
      "focus:valid:!border-red-500",
      "active:!border-red-500",
      "active:valid:!border-red-500",
      "valid:!border-red-500"
    );
    this.pwAlertEl.classList.remove("opacity-0");
    this.pwAlertEl.setAttribute("aria-hidden", "false");
  }

  showLoader() {
    this.loaderMsg.textContent = "Setting up...";
    // Show loader with animation
    this.loaderContainer.classList.add("opacity-0");
    setTimeout(() => {
      this.loaderContainer.classList.remove("hidden");
      this.loaderContainer.setAttribute("aria-hidden", "false");
    }, 5);
    setTimeout(() => {
      this.loaderContainer.classList.remove("opacity-0");
    }, 20);
  }

  stopLoader() {
    setTimeout(() => {
      this.loaderContainer.classList.add("opacity-0");
    }, 350);

    setTimeout(() => {
      this.isLoading = false;
      this.loaderContainer.classList.add("hidden");
      this.loaderContainer.setAttribute("aria-hidden", "true");
    }, 650);
  }
}

const setLoader = new Loader();
const setResume = new Resume();
const setCheck = new Checkbox();
const setStateServ = new ServerCheck();
const setSubmit = new SubmitForm();
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
  <main class="grid grid-cols-2 align-middle items-center min-h-screen">
    <!--form -->
    <div
      class="mx-4 lg:mx-0 col-span-2 h-full flex flex-col items-center justify-center"
    >
      <div class="bg-gray-50 rounded px-4 pt-10 pb-4 w-full max-w-[550px]">
        <div class="flex justify-center">
          <img
            class="max-w-60 max-h-30 mb-6"
            alt="logo"
            src="data:image/png;base64,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FIKy015kAH9vfYkAqDj5f8fwj+/hcgAluf0Nbe0XwbJmNH8HDyesvl5805pYtqNqwcJ/EZG74eoHmwVCNaPKZQXWClDjdjg0tBgiOX3IJdApBd/P7AJ1rSNG9wIybPDnFTeFPxU4riVwFNgogz+NyA13tzQuud/vIDK1+b5vHgTwzuraRf8G6GKcuJGmAqeiD0rKWNSyaskrfsfippbE0t9X1X3lMlHjXgDn+R2Pw/ao6POGafwq1Jf6tdODAINuV+KObgDPnvyPHHQyifS433EMpuaD8eG92hMCgFgSIwEghXBIjNRwABBIiWlqOQAYCJVC0jEAMCEVIhpRGJ0GdGszmp9FIliJm9O1rlj645q6elHF/2CI/w5WQ3+UyfMMwW9UUet2PDS0mGYo16p0zsCxIC4lcFSMPaLq2zHaAeJLEtu1BI5hGhvU4CEl5LnmcG/6i34HkQNtaVzyzZobv/qAmum7objK74AoR6JPC2RhS2Jp4N+cOaU1sezlmus+eynKhn1CRW8BkNkMBWckAXRB0QlBH4B2iPYB0glFFyBJAEcBpAQ4CtWkKdplqNGphtkninZV6VNop0ioC5JOAjja3RNrO1kmTDRknVE5mGlrTUFqTjT8qLpu4eMw5XMQfSsgM+FupXrwKO5pbcxsdmCqPJoIdSYXw9uf91TkKsp6ckrgqMoUCGtwzmRq2JUEjqhyntsJk6bUfaH05AdennHvF1NpZD16eu9ybX0iC6aZ/n4hf0re/MvFLYjH31T9SvKTULnI73goO2rgN62Jht/6HYcfmh/+bhLA91BXd+dZ6arLzbDxdpjGVIE5TBWGiqgAKVWkRLUPhvQKJK2qfRCzQ1T6TNEjhhq9apjHVXHcAHrTYhwJqdmngg6BdBum9qCk71gqFe5rTSw76vffm4iKR0tiaTOAz576c1XdVyoNGCWGqcNShpbDDEeB9AiIxAxoKYBKqBE1xawQSAWAEqgU5vHaosnysr76TJ++7afxnqraRR8TxXvdDIuGEu3NtcVVoQ+Lyl+cjqjQGV1Hd7ixror8WkwU5EmqTotJrAKco0ZERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERERDmfgdABEREREVD1W9HMDFAKYB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"
          />
        </div>
        <h1 class="block text-center font-bold text-3xl">
          {{ $t("setup_title") }}
        </h1>
        <form
          class="grid grid-cols-12 md:gap-x-6 justify-items-center"
          id="setup-form"
          action="setup"
          method="POST"
          autocomplete="off"
        >
          <h2 class="col-span-12 block text-left font-bold my-4 text-2xl">
            {{ $t("setup_account") }}
          </h2>
          <!-- username inpt-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('setup_username')"
              name="username"
              pattern="(.*?)"
              :placeholder="$t('setup_username_placeholder')"
              type="text"
              :required="true"
              :maxlength="256"
            />
          </AccountInpGroup>
          <!-- end username inpt-->
          <!-- password inpt-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('setup_password')"
              name="password"
              pattern="(.*?)"
              :placeholder="$t('setup_password_placeholder')"
              type="password"
              :required="true"
              :maxlength="256"
            />
          </AccountInpGroup>
          <!-- end password inpt-->
          <!-- password inpt-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('setup_password_check_=')"
              name="password_check"
              pattern="(.*?)"
              :placeholder="$t('setup_password_check_placeholder')"
              type="password"
              :required="true"
              :maxlength="256"
            />
          </AccountInpGroup>
          <!-- end password inpt-->
          <h2 class="col-span-12 block text-left font-bold mb-4 mt-2 text-2xl">
            {{ $t("setup_settings") }}
          </h2>
          <!-- ui host-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('setup_ui_host')"
              name="ui_host"
              pattern="^https?:\/\/.{1,255}(:((6553[0-5])|(655[0-2][0-9])|(65[0-4][0-9]{2})|(6[0-4][0-9]{3})|([1-5][0-9]{4})|([0-5]{0,5})|([0-9]{1,4})))?$"
              :placeholder="$t('setup_ui_host__placeholder')"
              type="text"
              :required="true"
            />
          </AccountInpGroup>
          <!-- end ui host-->
          <!-- ui url-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('setup_ui_url')"
              name="ui_url"
              pattern="\/(.*[a-z])"
              :placeholder="$t('setup_ui_url_placeholder')"
              type="text"
              :required="true"
            />
          </AccountInpGroup>
          <!-- end ui url-->
          <!-- server name-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('setup_server_name')"
              name="server_name"
              pattern=".*"
              :placeholder="$t('setup_server_name_placeholder')"
              type="text"
              value="www.example.com"
              :required="true"
            />
          </AccountInpGroup>
          <!-- end server name-->
          <div
            class="flex flex-col relative col-span-12 my-3 mx-2 max-w-[400px] w-full"
          >
            <h5
              class="text-base my-1 transition duration-300 ease-in-out text-md font-bold m-0"
            >
              Check server name DNS
            </h5>
            <div class="flex justify-start items-center">
              <button
                id="check-server-name"
                class="flex justify-start w-fit tracking-wide inline-block px-6 py-3 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer bg-primary hover:bg-primary/80 focus:bg-primary/80 leading-normal text-xs ease-in shadow-xs bg-150 bg-x-25 hover:-translate-y-px active:opacity-85 hover:shadow-md"
              >
                <span>check</span>
                <span
                  aria-check-color
                  class="block ml-2 rounded-full w-4 h-4 bg-gray-300"
                  aria-description="show state of server name"
                ></span>
                <span class="sr-only" aria-check-result></span>
              </button>
            </div>
          </div>
          <!-- auto let's encrypt-->
          <AccountInpGroup>
            <AccountInput
              :label="$t('setup_lets_encrypt')"
              name="lets_encrypt"
              :placeholder="$t('setup_lets_encrypt_placeholder')"
              value="no"
              :required="true"
            />
          </AccountInpGroup>
          <!-- end auto let's encrypt-->
          <div
            class="p-2 col-span-12 bg-gray-200 mt-4 md:mt-6 mb-1 py-2 px-2 rounded flex flex-col justify-center items-center w-full max-w-[400px] overflow-hidden"
          >
            <h5
              class="text-sm md:text-base text-center mt-1 mb-2 transition duration-300 ease-in-out text-md font-bold m-0"
            >
              {{ $t("setup_final_url") }}
            </h5>
            <p
              class="family-text text-center text-sm md:text-base break-words w-full px-4"
              data-resume
            >
              http://
            </p>
          </div>
          <div class="col-span-12 flex justify-center">
            <button
              type="submit"
              id="setup-button"
              name="setup-button"
              value="setup"
              class="tracking-wide my-4 inline-block px-6 py-3 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer bg-primary hover:bg-primary/80 focus:bg-primary/80 leading-normal text-sm ease-in shadow-xs bg-150 bg-x-25 hover:-translate-y-px active:opacity-85 hover:shadow-md"
            >
              {{ $t("setup_button") }}
            </button>
          </div>
        </form>
      </div>
    </div>
    <!-- end form -->
  </main>
</template>
