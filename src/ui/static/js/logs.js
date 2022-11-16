var current_container_id = null;
var last_logs_update = null;
var filter = "";
var date_filter1 = "";
var date_filter2 = "";

$(document).ready(function () {
  $("#date-picker").datepicker({ format: "yyyy/mm/dd" });
  current_container_id = $("#active-nav").data("container-id");
  const logs_interval = setInterval(load_logs, 1000);

  function clear_filters() {
    filter = "";
    date_filter1 = "";
    date_filter2 = "";
    $("#logs-list li").filter(function () {
      $(this).toggle(true);
    });
  }

  async function get_logs(container_id, last_update) {
    const response = await fetch(
      `${location.href}/${container_id}` +
        (last_update ? `?last_update=${last_update}` : "")
    );

    if (response.status === 200) {
      return await response.json();
    } else {
      console.log(`Error: ${response.status}`);
      clearInterval(logs_interval);
    }

    return null;
  }

  async function load_logs() {
    logs = await get_logs(current_container_id, last_logs_update);

    if (logs) {
      last_logs_update = logs.last_update;
      logs.logs.forEach((log) => {
        const log_element = document.createElement("li");
        log_element.className = "list-group-item";

        if (log.type === "error") {
          log_element.classList.add("list-group-item-danger");
        } else if (log.type === "warning") {
          log_element.classList.add("list-group-item-warning");
        } else if (log.type === "info") {
          log_element.classList.add("list-group-item-info");
        }

        log_element.innerHTML = log.content;

        if (
          !(
            log.content.toLowerCase().indexOf(filter) > -1 &&
            (log.content.toLowerCase().indexOf(date_filter1) > -1 ||
              log.content.toLowerCase().indexOf(date_filter2) > -1)
          )
        ) {
          log_element.style = "display: none;";
        }

        if (log.separator) log_element.classList.add("pt-1");

        document.getElementById("logs-list").appendChild(log_element);
      });
    }
  }

  $("#date-picker").on("changeDate", function () {
    let date = $(this).datepicker("getFormattedDate");

    if (date) {
      date_filter1 = date;
      date_filter2 = date.replaceAll("/", "-");
      $("#date-input").val(date);
      $("#date-clear").show();
      $("#logs-list li").filter(function () {
        $(this).toggle(
          $(this).text().toLowerCase().indexOf(filter) > -1 &&
            ($(this).text().toLowerCase().indexOf(date_filter1) > -1 ||
              $(this).text().toLowerCase().indexOf(date_filter2) > -1)
        );
      });
    }
  });

  $("#filter-input").on("keyup", function () {
    var val = $.trim(this.value);

    if (!val) {
      val = "";

      if (!$("#date-picker").datepicker("getFormattedDate")) {
        $("#date-clear").hide();
      }
    } else {
      $("#date-clear").show();
    }

    val = val.toLowerCase();
    filter = val;
    $("#logs-list li").filter(function () {
      $(this).toggle(
        $(this).text().toLowerCase().indexOf(val) > -1 &&
          ($(this).text().toLowerCase().indexOf(date_filter1) > -1 ||
            $(this).text().toLowerCase().indexOf(date_filter2) > -1)
      );
    });
  });

  $("#date-clear").click(function () {
    $("#filter-input").val("");
    $("#date-input").val("");
    $(this).hide();
    clear_filters();
  });

  $("#refresh-logs").click(function () {
    if ($(this).find("#rotate-icon").hasClass("rotate")) {
      $(this).find("#rotate-icon").removeClass("rotate");
      clearInterval(logs_interval);
    } else if (!$(this).find("#rotate-icon").hasClass("rotate")) {
      $(this).find("#rotate-icon").addClass("rotate");
      logs_interval = setInterval(load_logs, 1000);
    }
  });

  $(".container-selector").click(function () {
    clearInterval(logs_interval);
    current_container_id = $(this).data("container-id");
    $("#logs-list").empty();
    clear_filters();
    last_logs_update = null;
    let old_selector = $("#active-nav");
    old_selector.removeClass("active");
    old_selector.removeAttr("aria-current");
    old_selector.removeAttr("id");
    $(this).addClass("active");
    $(this).attr("aria-current", "page");
    $(this).attr("id", "active-nav");

    if (current_container_id == "linux") {
      $("#date-picker").prop("disabled", true);
    } else {
      $("#date-picker").prop("disabled", false);
    }

    load_logs();
    setTimeout(function () {
      logs_interval = setInterval(load_logs, 1000);
    }, 1000);
  });

  $("#filter-input").on("keypress", function (e) {
    var code = e.keyCode || e.which;
    if (code == 13) {
      e.preventDefault();
      return false;
    }
  });
});
