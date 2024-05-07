from wtforms import Form
from wtforms.fields import Field, StringField, BooleanField, SelectField, PasswordField, FormField
from wtforms.validators import Regexp
from wtforms.widgets import CheckboxInput

from re import search

class BWBooleanField(Field):

    widget = CheckboxInput()
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