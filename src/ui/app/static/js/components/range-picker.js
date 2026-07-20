window.BWRangePicker = (function () {
  const PRESET_SECONDS = {
    "1h": 3600,
    "24h": 86400,
    "7d": 604800,
    "30d": 2592000,
  };

  function init(elementId) {
    const root = document.getElementById(elementId);
    if (!root) return null;
    const buttons = root.querySelectorAll(".range-btn");
    const fpInput = root.querySelector(".range-fp");
    let flatpickrInstance = null;

    function computeRange(preset, customStart, customEnd) {
      const end = Math.floor(Date.now() / 1000);
      if (preset === "custom" && customStart && customEnd) {
        return { startEpoch: customStart, endEpoch: customEnd };
      }
      const seconds = PRESET_SECONDS[preset] || PRESET_SECONDS["24h"];
      return { startEpoch: end - seconds, endEpoch: end };
    }

    function setActive(preset, customStart, customEnd) {
      buttons.forEach((btn) => {
        const on = btn.dataset.range === preset;
        btn.classList.toggle("active", on);
        btn.setAttribute("aria-pressed", String(on));
      });
      const range = computeRange(preset, customStart, customEnd);
      root.dispatchEvent(
        new CustomEvent("change", { detail: { value: preset, ...range } }),
      );
    }

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const preset = btn.dataset.range;
        if (preset === "custom") {
          if (!flatpickrInstance && window.flatpickr && fpInput) {
            flatpickrInstance = flatpickr(fpInput, {
              mode: "range",
              maxDate: "today",
              onClose: (dates) => {
                if (dates.length === 2) {
                  // flatpickr's range mode returns both endpoints at local midnight. The DB
                  // window is half-open [start, end): pushing the end to the *next* midnight
                  // (+86400s) includes the full selected end-day instead of dropping it --
                  // and makes a same-day pick span a full 24h instead of start === end.
                  // ponytail: +86400s is "next local midnight" except when the selected end-day
                  // is itself a DST-transition day (23h/25h), where it's off by up to 3600s --
                  // negligible for an hourly dashboard; use a calendar-day-add if that matters.
                  setActive(
                    "custom",
                    Math.floor(dates[0].getTime() / 1000),
                    Math.floor(dates[1].getTime() / 1000) + 86400,
                  );
                }
              },
            });
          }
          if (flatpickrInstance) flatpickrInstance.open();
        } else {
          setActive(preset);
        }
      });
    });

    return { setActive };
  }

  return { init };
})();
