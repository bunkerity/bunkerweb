function addReasonOption(endpoint, reasons) {
  let content = "";

  reasons.forEach((reason, id) => {
    content += `<button
        role="option"
        data-${endpoint}-setting-select-dropdown-btn="reason"
        value="${reason}"
        class="${
          id === reasons.length - 1 ? "rounded-b" : ""
        } border-b border-l border-r border-gray-300 dark:hover:brightness-90 hover:brightness-90 bg-white text-gray-700 my-0 relative py-2 px-3 text-left align-middle transition-all rounded-none cursor-pointer leading-normal text-sm ease-in tracking-tight-rem dark:border-slate-600 dark:bg-slate-700 dark:text-gray-300"
    >
    ${reason}
  </button>`;
  });
}
