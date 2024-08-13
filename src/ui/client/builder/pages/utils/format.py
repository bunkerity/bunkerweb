def get_fields_from_field(field):
    # get field["data"] and add inpType
    return {"setting": {**field["data"], "inpType": field["type"].lower()}}
