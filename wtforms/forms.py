from wtforms import Form
from wtforms.fields import Field, StringField, BooleanField, SelectField, PasswordField, FormField
from wtforms.validators import Regexp
from wtforms.widgets import CheckboxInput



from re import search

class CheckboxSettingWidget(CheckboxInput):
    def __init__(self, error_class='has_errors'):
        super(CheckboxInput, self).__init__()
        self.error_class = error_class

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        kwargs.setdefault('name', field.name)
        kwargs.setdefault('type', 'checkbox')
        kwargs.setdefault('data-default-method', "mode" if kwargs['name'] in ('AUTOCONF_MODE', 'SWARM_MODE', 'KUBERNETES_MODE') else field.method if hasattr(field, 'method') else 'default')
        kwargs.setdefault('value', field.global_config_value)
        kwargs.setdefault('data-pattern', field.regex)

        kwargs.setdefault('checked', "")
        return f"""<div data-checkbox-handler="{kwargs['id']}"> 
            class="relative mb-7 md:mb-0 z-10 ">
            {self.input(field, **kwargs)} {self.label(field, {"class": "sr-only", "for": kwargs['name']})}
        <input id="{kwargs['name']}"
                name="{kwargs['name']}"
                data-default-method="{% if inp_name in ['AUTOCONF_MODE', 'SWARM_MODE', 'KUBERNETES_MODE'] %}mode{% else %}{{ global_config_method }}{% endif %}"
                data-default-value="{{ global_config[inp_name]['value'] }}"
                {% if inp_name in ['AUTOCONF_MODE', 'SWARM_MODE', 'KUBERNETES_MODE'] or global_config_method != 'ui' and global_config_method != 'default' or is_read_only %} disabled {% endif %}
                data-checked="{% if global_config_value == "yes" %}true{% else %}false{% endif %}"
                {% if global_config_value == "yes" %}checked{% endif %}
                id="checkbox-{kwargs['id']}"
                class="checkbox"
                type="checkbox"
                data-pattern="{{ inp_regex|safe }}"
                value="{{ global_config_value }}"
                {% if is_multiple %} data-is-multiple {% endif %}
                />
        <svg data-checkbox-handler="{kwargs['id']}"
                class="pointer-events-none	absolute fill-white dark:fill-gray-300 left-0 top-0 translate-x-1 translate-y-2 h-3 w-3"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 512 512">
            <path class="pointer-events-none" d="M470.6 105.4c12.5 12.5 12.5 32.8 0 45.3l-256 256c-12.5 12.5-32.8 12.5-45.3 0l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0L192 338.7 425.4 105.4c12.5-12.5 32.8-12.5 45.3 0z">
            </path>
        </svg>
    </div>
"""


class BWBooleanField(Field):

    widget = CheckboxSetting()
    false_values = (False, "false", "")

    def __init__(self, label=None, validators=None, false_values=None, **kwargs):
        super().__init__(label, validators, **kwargs)
        if false_values is not None:
            self.false_values = false_values

    def pre_validate(self, form):
        if isinstance(self.data, bool):
            self.data = "no"

    def process_data(self, value):
        self.data = value

    def process_formdata(self, valuelist):
        if not valuelist or valuelist[0] in self.false_values:
            self.data = False
        else:
            self.data = "yes"

    def _value(self):
        if self.raw_data:
            return str(self.raw_data[0])
        return "yes"

def number_from_setting_name(setting):
    res = search(r"_([0-9]+)$", setting)
    if res:
        return res.group(1)
    return "0"

def settings_to_form(settings):
    class SettingsForm(Form):
        pass
    bw_multiple_forms = {}
    for setting, data in settings.items():
        field_type = None
        field_data = dict(
            label=data["label"],
            validators=[Regexp(data["regex"])],
            description=data["help"],
            id=setting,
            default=data["default"],
            # widget=None,
            render_kw={
                "custom-attributes-1": "custom-value-1",
                "custom-attributes-2": "custom-value-2",
            },
            name=setting,
            # _form=None,
            # _prefix='',
            # _translations=None,
            # _meta=None
        )
        if data["type"] == "text":
            field_type = StringField
        elif data["type"] == "check":
            field_type = BWBooleanField
            del field_data["default"]
            if data["default"] == "yes":
                field_data["default"] = "checked"
                field_data["render_kw"]["checked"] = ""
            field_data["false_values"] = ("no")
        elif data["type"] == "select":
            field_type = SelectField
            field_data["choices"] = data["select"]
        elif data["type"] == "password":
            field_type = PasswordField
        else:
            print(f"unsupported type {data['type']}")
            continue
        if "multiple" not in data:
            setattr(
                SettingsForm,
                setting,
                field_type(
                    **field_data
                )
            )
        else:
            class BWMultipleForm(Form):
                pass
            multiple_key = f"{data['multiple']}-{number_from_setting_name(setting)}"
            if multiple_key not in bw_multiple_forms:
                bw_multiple_forms[multiple_key] = BWMultipleForm
            setattr(
                bw_multiple_forms[multiple_key],
                setting,
                field_type(
                    **field_data
                )
            )
    for multiple, form in bw_multiple_forms.items():
        setattr(
            SettingsForm,
            multiple,
            FormField(form)
        )
    return SettingsForm

def compute_form(client_form, request_form, settings):
    for key, value in request_form.items():
        print(key)
        real_key = key
        res = search(r"([a-z\-]+\-[0-9]+\-).*_([0-9]+)$", key)
        if res:
            real_key = "_".join(key.replace(res.group(1), "").split("_")[:-1])
        if real_key in settings and "multiple" in settings[real_key]:
            setattr(
                client_form,
                key,
                StringField(
                    validators=[Regexp(settings[real_key]["regex"])]
                )
            )
    return client_form