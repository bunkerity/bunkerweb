var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
	return new bootstrap.Tooltip(tooltipTriggerEl, { container: 'body' })
})

function post(operation, url, data) {
	var form = document.createElement("form");
	form.method = "POST";
	form.action = url;
	for (var key in data) {
		var field = document.createElement("input");
		field.type = "hidden";
		field.name = key;
		field.value = data[key];
		form.appendChild(field);
	}
	var field = document.createElement("input");
	field.type = "hidden";
	field.name = "operation";
	field.value = operation;
	form.appendChild(field);
	document.body.appendChild(form);
	form.submit();
}

function getData(id) {
	var elements = document.getElementById(id).elements;
	var data = {};
	for (var i = 0; i < elements.length; i++) {
		element = elements[i];
		if (element["type"] === "checkbox") {
			if (element["checked"]) {
				data[element["name"]] = "yes";
			}
			else {
				data[element["name"]] = "no";
			}
		}
		else {
			data[element["name"]] = element["value"];
		}
	}
	return data;
}

function newService() {
	post("new", "services", getData('form-new'));
}

function editService(id) {
	post("edit", "services", getData('form-edit-' + id));
}

function deleteService(id) {
	post("delete", "services", getData('form-delete-' + id));
}

function reloadInstance(id) {
	post("reload", "instances", getData('form-instance-' + id));
	return false;
}

function startInstance(id) {
	post("start", "instances", getData('form-instance-' + id));
	return false;
}

function stopInstance(id) {
	post("stop", "instances", getData('form-instance-' + id));
	return false;
}

function restartInstance(id) {
	post("restart", "instances", getData('form-instance-' + id));
	return false;
}

function deleteInstance(id) {
	post("delete", "instances", getData('form-instance-' + id));
	return false;
}

var multiples = {};
function addMultiple(id, paramsEnc) {
	var params = JSON.parse(paramsEnc);
	var div = document.getElementById(id);
	if (!multiples.hasOwnProperty(id)) {
		multiples[id] = 0;
	}
	multiples[id]++;
	for (var i = 0; i < params.length; i++) {
		var input = "";
		var input_id = id + "-" + params[i]["id"] + "-" + multiples[id].toString();
		var input_name = params[i]["env"] + "_" + multiples[id].toString();
		var input_label = params[i]["label"] + " #" + multiples[id].toString();
		var input_value = params[i]["default"];
		var pt = "";
		if (params[i]["type"] == "text") {
			input = `<input type="text" class="form-control" id="${input_id}" value="${input_value}" name="${input_name}">`;
		}
		else if (params[i]["type"] == "checkbox") {
			if (input_value == "yes") {
				input_value = "checked";
			}
			input = `<div class="form-check form-switch"><input type="checkbox" class="form-check-input" id="${input_id}" name="${input_name}" ${input_value}></div>`;
			pt = "pt-0";
		}
		div.insertAdjacentHTML('beforeend', `<label for="${input_id}" class="col-4 col-form-label ${pt} mb-3" id="label-${input_id}">${input_label}</label><div class="col-8 mb-3" id="input-${input_id}">${input}</div>`);
	}
}

function delMultiple(id, paramsEnc) {
	if (multiples.hasOwnProperty(id) && multiples[id] > 0) {
		var params = JSON.parse(paramsEnc);
		for (var i = 0; i < params.length; i++) {
			var input_id = id + "-" + params[i]["id"] + "-" + multiples[id].toString();
			document.getElementById("label-" + input_id).remove();
			document.getElementById("input-" + input_id).remove();
		}
		multiples[id]--;
	}
}
