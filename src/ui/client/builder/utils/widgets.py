
from typing import Union

# Add params to data dict only if value is not the default one
def add_key_value(data, key, value, default):
    if value == default:
        return
    data[key] = value
        