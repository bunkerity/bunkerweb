std             = "ngx_lua"
unused_args     = false
redefined       = false
max_line_length = false


not_globals = {
    "string.len",
    "table.getn",
}


ignore = {
    "6.", -- ignore whitespace warnings
}
