def add_column(title, field, formatter=""):
    # don"t return formatter if ""
    if formatter:
        return {"title": title, "field": field, "formatter": formatter}

    return {"title": title, "field": field}
