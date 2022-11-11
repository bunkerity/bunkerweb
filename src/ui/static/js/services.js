var multiples = {};
function addMultiple(id, paramsEnc) {
  var params = JSON.parse(paramsEnc);
  var div = document.getElementById(id);

  if (!multiples.hasOwnProperty(id)) {
    multiples[id] = 0;
  }

  multiples[id]++;
  x = 0;

  for (const param in params) {
    var input = "";
    var input_id =
      id + "-" + params[param]["id"] + "-" + multiples[id].toString();
    var input_name =
      params[param]["env"] +
      (multiples[id] - 1 > 0 ? "_" + (multiples[id] - 1).toString() : "");
    var input_label = params[param]["label"] + " #" + multiples[id].toString();
    var input_value = params[param]["default"];
    var input_help = params[param]["help"];
    var input_selects = params[param]["select"];
    var pt = "";
    var padding_bottom = "";

    if (params[param]["type"] == "text" || params[param]["type"] == "number") {
      input = `<input type="${params[param]["type"]}" class="form-control" id="${input_id}" value="${input_value}" name="${input_name}">`;
    } else if (params[param]["type"] == "check") {
      if (input_value == "yes") {
        input_value = "checked";
      } else {
        input_value = "";
      }

      input = `<div class="form-check form-switch"><input type="checkbox" class="form-check-input" role="switch" id="${input_id}" name="${input_name}" ${input_value}><input type="hidden" id="${input_id}-hidden" name="${input_name}" value="off"></div>`;
      pt = "pt-0";
    } else if (params[param]["type"] == "select") {
      input = `<select type="form-select" class="form-control form-select" id="${input_id}" name="${input_name}">`;
      for (const select in input_selects) {
        selected = "";
        if (input_value == select) {
          selected = "selected";
        }

        input += `<option value="${select}" ${selected}>${select}</option>`;
      }
      input += `</select>`;
    }

    if (x === 0 && multiples[id] > 1) {
      padding_bottom = "pb-3";
    }

    div.insertAdjacentHTML(
      "afterend",
      `<div class="d-flex flex-row justify-content-between align-items-center mb-3 ${padding_bottom}" id="${input_id}"><div class="px-2 d-sm-inline" data-bs-toggle="tooltip" data-bs-placement="bottom" title="${input_help}"><i class="fas fa-question-circle"></i></div><label for="${input_id}" class="flex-grow-1 d-sm-inline ${pt}" id="${input_id}">${input_label}</label><div class="d-sm-inline" id="${input_id}">${input}</div></div>`
    );
    x++;
  }
}

function delMultiple(id, paramsEnc) {
  if (multiples.hasOwnProperty(id) && multiples[id] > 0) {
    var params = JSON.parse(paramsEnc);
    for (const param in params) {
      var input_id =
        id + "-" + params[param]["id"] + "-" + multiples[id].toString();
      document.getElementById(input_id).remove();
    }
    multiples[id]--;
  }
}

$(document).ready(function () {
  $("form").on("focus", ".form-control", function () {
    if (
      ["text", "number"].includes($(this).attr("type")) &&
      $(this).prop("validity").valid
    ) {
      $(this).addClass("is-valid");
    }
  });

  $("form").on("focusout", ".form-control", function () {
    if (["text", "number"].includes($(this).attr("type"))) {
      $(this).removeClass("is-valid");
    }
  });

  $("form").on("change", ".form-control", function () {
    if (["text", "number"].includes($(this).attr("type"))) {
      if (!$(this).prop("validity").valid) {
        $("#pills-tab a").addClass("disabled");
        $(this).addClass("is-invalid");
      } else {
        $("#pills-tab a").removeClass("disabled");
        $(this).removeClass("is-invalid");
        $(this).addClass("is-valid");
      }
    }
  });
});
