<script setup>
import { reactive, defineProps, onMounted, onUnmounted } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";
import Clipboard from "@components/Forms/Feature/Clipboard.vue";
import { useUUID } from "@utils/global";

import flatpickr from "flatpickr";
import "@assets/css/flatpickr.min.css";
import "@assets/css/flatpickr.dark.min.css";

/** 
  @name Forms/Field/Datepicker.vue
  @description This component is used to create a complete datepicker field input with error handling and label.
  You can define a default date, a min and max date, and a format.
  We can also add popover to display more information.
  It is mainly use in forms.
  @example
  { 
    id: 'test-date',
    columns : {"pc": 6, "tablet": 12, "mobile": 12},
    disabled: false,
    required: true,
    value: 1735682600000,
    minDate: 1735682600000,
    maxDate: 1735689600000,
    inpClass: "text-center",
    inpType : ""
    popovers : [
      {
        text: "This is a popover text",
        iconName: "info",
      },
    ],
  }
  @param {string} [id=uuidv4()] - Unique id 
  @param {string} label - The label of the field. Can be a translation key or by default raw text.
  @param {string} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
  @param {array} popovers - List of popovers to display more information
  @param {string} [inpType="datepicker"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
  @param {number<timestamp>} [value=""] - Default date when instanciate
  @param {number<timestamp>} [minDate=""] - Impossible to pick a date before this date. 
  @param {number<timestamp>} [maxDate=""] - Impossible to pick a date after this date.
  @param {boolean} [isClipboard=true] - allow to copy the timestamp value
  @param {boolean} [hideLabel=false]
  @param {object} [columns={"pc": "12", "tablet": "12", "mobile": "12}] - Field has a grid system. This allow to get multiple field in the same row if needed.
  @param {boolean} [disabled=false]
  @param {boolean} [required=false]
  @param {string} [headerClass=""]
  @param {string} [containerClass=""]
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const props = defineProps({
  // id && type && disabled && required && value
  id: {
    type: String,
    required: false,
    default: "",
  },
  name: {
    type: String,
    required: true,
  },
  label: {
    type: String,
    required: true,
  },
  value: {
    type: [String, Number, Date],
    required: false,
    default: "",
  },
  popovers: {
    type: Array,
    required: false,
    default: [],
  },
  inpType: {
    type: String,
    required: false,
    default: "datepicker",
  },
  isClipboard: {
    type: Boolean,
    required: false,
    default: true,
  },
  hideLabel: {
    type: Boolean,
    required: false,
  },
  headerClass: {
    type: String,
    required: false,
    default: "",
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  inpClass: {
    type: String,
    required: false,
    default: "",
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: false,
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
  required: {
    type: Boolean,
    required: false,
    default: false,
  },
  minDate: {
    type: [String, Number],
    required: false,
    default: "",
  },
  maxDate: {
    type: [String, Number],
    required: false,
    default: "",
  },
  tabId: {
    type: [String, Number],
    required: false,
    default: contentIndex,
  },
});

const date = reactive({
  id: "",
  isValid: true,
  format: "m/d/Y H:i:S",
  currStamp: "",
});

const picker = reactive({
  isOpen: false,
});

let datepicker;

function setMonthSelect(calendar, id) {
  // Hide default select and optionss
  const defaultSelect = calendar.querySelector(
    ".flatpickr-monthDropdown-months"
  );
  defaultSelect.classList.add("hidden");
  defaultSelect.setAttribute("aria-hidden", "true");
  defaultSelect.setAttribute("tabindex", "-1");
  defaultSelect.querySelectorAll("option").forEach((option) => {
    option.classList.add("hidden");
    option.setAttribute("tabindex", "-1");
    option.setAttribute("aria-hidden", "true");
  });
  // Create custom select

  // Container
  const container = document.createElement("div");
  container.classList.add(
    "flatpickr-monthDropdown-months",
    "inline",
    "relative"
  );
  // Select-like
  const selectCustom = document.createElement("button");
  selectCustom.setAttribute("data-interactive", "");
  selectCustom.setAttribute("aria-label", "Month");
  selectCustom.setAttribute("data-months-select", "");
  selectCustom.setAttribute("aria-controls", `${id}-custom`);
  container.appendChild(selectCustom);

  // Options container
  const optCtnr = document.createElement("div");
  optCtnr.setAttribute("role", "radiogroup");
  optCtnr.setAttribute("id", `${id}-custom`);
  optCtnr.classList.add("select-dropdown-container", "hidden", "flex");
  container.appendChild(optCtnr);
  // Options
  calendar
    .querySelector(".flatpickr-monthDropdown-months")
    .querySelectorAll("option")
    .forEach((option) => {
      // Prepare options
      const opt = document.createElement("button");
      opt.classList.add(
        "flatpickr-monthDropdown-month",
        "rounded-none",
        "text-white",
        "py-1",
        "hover:brightness-125",
        "focus:brightness-125"
      );
      opt.setAttribute("data-month", option.value);
      opt.setAttribute("data-value", option.value);
      opt.setAttribute("data-interactive", "");
      opt.setAttribute("role", "radio");
      opt.setAttribute("aria-checked", option.selected ? "true" : "false");
      opt.setAttribute("aria-label", option.textContent);
      opt.setAttribute("aria-controls", `${id}-custom`);
      opt.textContent = option.textContent;
      // Set select as button content
      if (option.selected) {
        selectCustom.textContent = option.textContent;
      }
      // Append options
      optCtnr.appendChild(opt);
    });

  // Insert as sibling of select
  defaultSelect.parentNode.insertBefore(container, defaultSelect.nextSibling);
}

function setPickerAtt(calendarEl, id = false) {
  // change error non-standard attributes
  const inps = calendarEl.querySelectorAll(
    'input.numInput[type="number"][maxlength]'
  );
  inps.forEach((inp) => {
    inp.setAttribute("data-maxlength", inp.getAttribute("maxlength"));
    inp.removeAttribute("maxlength");
  });
  // set role button
  calendarEl.querySelectorAll(".flatpickr-day").forEach((el) => {
    el.setAttribute("role", "button");
  });
  calendarEl
    .querySelector(".flatpickr-prev-month")
    .setAttribute("role", "button");
  calendarEl
    .querySelector(".flatpickr-next-month")
    .setAttribute("role", "button");
  // Prevent svg to be focusable
  calendarEl.querySelectorAll("svg").forEach((svg) => {
    svg.classList.add("pointer-events-none");
  });

  if (id) {
    calendarEl.setAttribute("id", `${id}-calendar`);
  }
}

function handleEvents(calendarEl, id, datepicker) {
  calendarEl.addEventListener("click", (e) => {
    // Close dropdown month select if click outside
    closeSelectByDefault(calendarEl, id, e);

    // Remove prev focus el and replace by click one if is tabindex element
    updateIndex(calendarEl, e.target);

    // When month change, update tabindex and update custom select
    if (
      e.target.classList.contains("flatpickr-prev-month") ||
      e.target.classList.contains("flatpickr-next-month") ||
      e.target.classList.contains("flatpickr-monthDropdown-month")
    ) {
      setIndex(calendarEl, contentIndex);
    }

    // When click on next or prev month button
    // Update custom select and options
    if (
      e.target.classList.contains("flatpickr-prev-month") ||
      e.target.classList.contains("flatpickr-next-month")
    ) {
      // Get update value
      const selectDefault = calendarEl.querySelector(
        "select.flatpickr-monthDropdown-months"
      );

      let monthValue;
      let monthName;

      selectDefault.querySelectorAll("option").forEach((option) => {
        if (option.selected) {
          monthValue = option.value;
          monthName = option.textContent;
        }
      });

      // Update options
      calendarEl.querySelectorAll("[data-month]").forEach((el) => {
        el.setAttribute("aria-checked", "false");
        el.classList.remove("active");

        if (el.getAttribute("data-month") === monthValue) {
          el.setAttribute("aria-checked", "true");
          el.classList.add("active");
        }
      });
      // Update select text
      const selectCustom = calendarEl.querySelector("[data-months-select]");
      selectCustom.textContent = monthName;
      selectCustom.focus();
    }

    // When click on custom select toggle
    toggleSelect(calendarEl, id, e);

    // When click on custom select option
    updateMonth(calendarEl, id, e, datepicker);
  });

  calendarEl.addEventListener("keydown", (e) => {
    // Space or enter  logic
    if (
      (e.key !== "Tab" && !e.shiftKey && e.keyCode === 13) ||
      (e.key !== "Tab" && !e.shiftKey && e.keyCode === 32)
    ) {
      // Prev or next month button
      if (
        e.target.classList.contains("flatpickr-prev-month") ||
        e.target.classList.contains("flatpickr-next-month")
      ) {
        e.preventDefault();
        e.target.click();
      }
      // Close dropdown month select if target isn't select
      closeSelectByDefault(calendarEl, id, e);
      // Custom select toggle
      toggleSelect(calendarEl, id, e);
      // Custom select option
      updateMonth(calendarEl, id, e, datepicker);
    }

    let prevEl = null;

    // Override default tab + maj behavior that focus input instead of previous calendar element
    if (e.key === "Tab" && e.shiftKey) {
      e.preventDefault();
      const currActive = calendarEl.querySelector(
        '[data-tabindex-active="true"]'
      );
      if (!currActive) return;

      try {
        // Case day, get prev day or next month el if no day remaining
        if (currActive.classList.contains("flatpickr-day"))
          prevEl =
            currActive.previousElementSibling ||
            calendarEl.querySelector(".flatpickr-next-month") ||
            null;

        // Case months
        if (currActive.classList.contains("flatpickr-next-month"))
          prevEl = calendarEl.querySelector(".cur-year") || null;

        if (currActive.hasAttribute("data-months-select"))
          prevEl = calendarEl.querySelector(".flatpickr-prev-month") || null;

        if (currActive.hasAttribute("data-month"))
          prevEl =
            currActive.previousElementSibling ||
            calendarEl.querySelector("[data-months-select]") ||
            null;

        // Case first datepicker element, go to input
        if (currActive.classList.contains("flatpickr-prev-month"))
          prevEl = null;

        // Case year
        if (currActive.classList.contains("cur-year"))
          prevEl = calendarEl.querySelector("[data-months-select]") || null;

        // Case hours
        if (currActive.classList.contains("flatpickr-hour"))
          prevEl =
            calendarEl.querySelector(".dayContainer").lastElementChild || null;

        // Case minutes
        if (currActive.classList.contains("flatpickr-minute"))
          prevEl = calendarEl.querySelector(".flatpickr-hour") || null;

        // Case minutes
        if (currActive.classList.contains("flatpickr-second"))
          prevEl = calendarEl.querySelector(".flatpickr-minute") || null;

        // Focus or close
        if (prevEl) prevEl.focus();

        if (!prevEl) {
          //Focus previous element with a tabindex
          const currIndex = datepicker.input.getAttribute("tabindex");
          const elements = document.querySelectorAll(
            `input[tabindex="${currIndex}"]`
          );
          // Remove disabled elements
          const filtered = [];
          elements.forEach((el) => {
            if (el === datepicker.input) return filtered.push(el);
            if (
              el.hasAttribute("disabled") ||
              el.className.includes("flatpickr")
            )
              return;
            filtered.push(el);
          });
          // Get previous element
          let focusEl;
          filtered.forEach((el, id) => {
            if (el !== datepicker.input) return;
            focusEl = filtered[id - 1];
          });
          // Focus new one
          datepicker.close();
          setTimeout(() => {
            focusEl.focus();
          }, 50);
        }
      } catch (e) {}
    }

    // Override when seconds
    if (
      e.keyCode === "Tab" &&
      !e.shiftKey &&
      calendarEl
        .querySelector('[data-tabindex-active="true"]')
        .classList.contains("flatpickr-second")
    ) {
      try {
        //Focus next element with a tabindex
        const currIndex = datepicker.input.getAttribute("tabindex");
        const elements = document.querySelectorAll(
          `input[tabindex="${currIndex}"]`
        );
        // Remove disabled elements
        const filtered = [];
        elements.forEach((el) => {
          if (el === datepicker.input) return filtered.push(el);
          if (el.hasAttribute("disabled") || el.className.includes("flatpickr"))
            return;
          filtered.push(el);
        });
        // Get next element
        let focusEl;
        filtered.forEach((el, id) => {
          if (el !== datepicker.input) return;
          focusEl = filtered[id + 1];
        });
        // Focus new one
        datepicker.close();
        setTimeout(() => {
          focusEl.focus();
        }, 50);
      } catch (e) {}
    }

    //  Global
    setPickerAtt(calendarEl, false);
    setIndex(calendarEl, contentIndex);
    return updateIndex(calendarEl, prevEl || document.activeElement);
  });
}

function toggleSelect(calendar, id, e) {
  if (e.target.hasAttribute("data-months-select")) {
    const optCtnr = calendar.querySelector(`#${id}-custom`);
    optCtnr.classList.toggle("hidden");
    optCtnr.setAttribute(
      "aria-hidden",
      optCtnr.classList.contains("hidden") ? "true" : "false"
    );
  }
}

function closeSelectByDefault(calendar, id, e) {
  if (!e.target.hasAttribute("data-months-select")) {
    const optCtnr = calendar.querySelector(`#${id}-custom`);
    if (!optCtnr.classList.contains("hidden")) {
      optCtnr.classList.add("hidden");
      optCtnr.setAttribute("aria-hidden", "true");
    }
  }
}

function updateMonth(calendar, id, e, datepicker) {
  if (e.target.hasAttribute("data-month")) {
    // Close dropdown
    const optCtnr = calendar.querySelector(`#${id}-custom`);
    optCtnr.classList.add("hidden");
    optCtnr.setAttribute("aria-hidden", "true");

    // Update options
    calendar.querySelectorAll("data-month").forEach((el) => {
      el.setAttribute("aria-checked", "false");
      el.classList.remove("active");
    });
    e.target.setAttribute("aria-checked", "true");
    e.target.classList.add("active");
    // Update select text
    const selectCustom = calendar.querySelector("[data-months-select]");
    selectCustom.textContent = e.target.textContent;
    selectCustom.focus();
    // Click on default select to update
    const selectDefault = calendar.querySelector(
      "select.flatpickr-monthDropdown-months"
    );
    selectDefault.querySelectorAll("option").forEach((option) => {
      if (option.value === e.target.getAttribute("data-month")) {
        datepicker.changeMonth(parseInt(option.value, 10) - 1, false);
        option.selected = true;
      }
    });
  }
}

function updateIndex(calendarEl, target) {
  if (target.hasAttribute("tabindex")) {
    calendarEl.querySelectorAll("[data-tabindex-active]").forEach((el) => {
      el.removeAttribute("data-tabindex-active");
    });

    target.setAttribute("data-tabindex-active", true);
  }
}

function setIndex(calendarEl, tabindex) {
  try {
    const days = calendarEl.querySelectorAll(".flatpickr-day");
    days.forEach((day) => {
      day.setAttribute("tabindex", tabindex);
    });
  } catch (e) {}

  try {
    const customSelectEls = calendarEl.querySelectorAll("[data-interactive]");

    customSelectEls.forEach((el) => {
      el.setAttribute("tabindex", tabindex);
    });
  } catch (err) {}

  try {
    const nextMonth = calendarEl.querySelector(".flatpickr-next-month");
    const prevMonth = calendarEl.querySelector(".flatpickr-prev-month");
    const year = calendarEl.querySelector(".cur-year");
    const monthSelect = calendarEl.querySelector(
      ".flatpickr-monthDropdown-months"
    );
    prevMonth.setAttribute("tabindex", tabindex);
    nextMonth.setAttribute("tabindex", tabindex);
    year.setAttribute("tabindex", tabindex);
    monthSelect.setAttribute("tabindex", tabindex);
    const months = calendarEl.querySelectorAll(
      ".flatpickr-monthDropdown-month"
    );
    months.forEach((month) => {
      month.setAttribute("tabindex", tabindex);
    });
  } catch (e) {}

  try {
    const hour = calendarEl.querySelector(".numInput.flatpickr-hour");
    const minute = calendarEl.querySelector(".numInput.flatpickr-minute");
    const second = calendarEl.querySelector(".numInput.flatpickr-second");

    hour.setAttribute("tabindex", tabindex);
    minute.setAttribute("tabindex", tabindex);
    second.setAttribute("tabindex", tabindex);
  } catch (e) {}
}

onMounted(() => {
  date.id = useUUID(props.id);
  datepicker = flatpickr(`#${date.id}`, {
    locale: "en",
    dateFormat: date.format,
    defaultDate: +props.value,
    maxDate: +props.maxDate ? +props.maxDate : "",
    minDate: +props.minDate ? +props.minDate : "",
    enableTime: true,
    enableSeconds: true,
    time_24hr: true,
    minuteIncrement: 1,
    onChange(selectedDates, dateStr, instance) {
      if (!dateStr && props.required) return (date.isValid = false);
      //Check if date is in interval
      try {
        const currStamp = Date.parse(dateStr);

        date.currStamp = currStamp;
        // Run whatever, if invalid this will override
        date.isValid = true;
      } catch (err) {}
    },
    onOpen(selectedDates, dateStr, instance) {
      picker.isOpen = true;
      // Focus on current date and update tabindex
      try {
        setIndex(instance.calendarContainer, contentIndex);
        const baseFocus =
          instance.calendarContainer.querySelector(".flatpickr-day.today") ||
          instance.calendarContainer.querySelector(".flatpickr-day");
        baseFocus.setAttribute("data-tabindex-active", true);
        setTimeout(() => {
          baseFocus.focus();
        }, 50);
      } catch (err) {}
    },
    onClose(selectedDates, dateStr, instance) {
      picker.isOpen = false;
      setIndex(instance.calendarContainer, "-1");
    },
  });
  // Check if multiple or not
  let datepickerEl = null;
  if (Array.isArray(datepicker)) {
    datepickerEl = datepicker[datepicker.length - 1];
  } else {
    datepickerEl = datepicker;
  }
  // Set valid date state
  if (!datepickerEl.selectedDates[0] && props.required) date.isValid = false;
  if (!datepickerEl.selectedDates[0] && !props.required) date.isValid = true;

  const calendar = datepickerEl.calendarContainer;
  // Impossible to use default select month dropdown with keyboard
  // We need to create our own and link calendar to it
  setMonthSelect(calendar, date.id);
  // Override default behavior that go to input el instead of previous calendat element on tab + maj
  handleEvents(calendar, date.id, datepickerEl);

  setPickerAtt(calendar, date.id);
});

onUnmounted(() => {
  datepicker.destroy();
});
</script>

<template>
  <Container
    :class="[picker.isOpen ? 'z-[100]' : '']"
    v-if="props.inpType === 'datepicker'"
    :containerClass="`${props.containerClass}`"
    :columns="props.columns"
  >
    <Header
      :popovers="props.popovers"
      :required="props.required"
      :name="props.name"
      :label="props.label"
      :id="date.id"
      :hideLabel="props.hideLabel"
      :headerClass="props.headerClass"
    />

    <div class="relative flex flex-col items-start">
      <input
        :data-timestamp="date.currStamp"
        :tabindex="props.tabId"
        :aria-controls="`${date.id}-calendar`"
        type="text"
        :class="[
          date.isValid ? 'valid' : 'invalid',
          'input-regular',
          props.inpClass,
          props.disabled ? 'cursor-not-allowed' : 'cursor-pointer',
        ]"
        :id="date.id"
        :required="props.required || false"
        :disabled="props.disabled || false"
        :name="props.name"
        :placeholder="'mm/dd/yyyy h:m:s'"
        pattern="/^(0[1-9]|1[0-2])\/(0[1-9]|1\d|2\d|3[01])\/\d{4}$/g"
      />
      <svg
        aria-hidden="true"
        role="img"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.5"
        stroke="currentColor"
        class="datepicker-svg"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5"
        />
      </svg>
      <Clipboard
        :isClipboard="props.isClipboard"
        :valueToCopy="date.currStamp"
        :clipboardClass="'datepicker-clip'"
        :copyClass="'datepicker-clip'"
      />
      <ErrorField
        :errorClass="'picker'"
        :isValid="date.isValid"
        :isValue="!!date.value"
      />
    </div>
  </Container>
</template>
