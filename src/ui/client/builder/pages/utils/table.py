def add_column(title, field, formatter="", minWidth=None):

    col = {"title": title, "field": field}

    if formatter:
        col["formatter"] = formatter

    if minWidth:
        col["minWidth"] = minWidth

    return col
