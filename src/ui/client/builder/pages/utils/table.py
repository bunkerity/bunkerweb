def add_column(title, field, formatter="", minWidth=None, maxWidth=None, visible=None):

    col = {"title": title, "field": field}

    if formatter:
        col["formatter"] = formatter

    if minWidth:
        col["minWidth"] = minWidth

    if maxWidth:
        col["maxWidth"] = maxWidth

    if visible is not None:
        col["visible"] = visible

    return col
