from wtforms import Form
from wtforms.fields import Field, StringField, BooleanField, SelectField, PasswordField
from wtforms.validators import Regexp
from wtforms.widgets import CheckboxInput

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

def settings_to_form(settings):
    class SettingsForm(Form):
        pass
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
        setattr(
            SettingsForm,
            setting,
            field_type(
                **field_data
            )
        )
    return SettingsForm


