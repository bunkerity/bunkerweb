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
			if (element["value"] === "on") {
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

function postNew() {
	post("new", "services", getData('form-new'));
}

function postEdit(id) {
	post("edit", "services", getData('form-edit-' + id));
}

function postDelete(id) {
	post("delete", "services", getData('form-delete-' + id));
}
