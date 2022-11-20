--std             = "ngx_lua+busted"
unused_args     = false
redefined       = false
max_line_length = false


globals = {
    --"_KONG",
    --"kong",
    --"ngx.IS_CLI",
}


not_globals = {
    "string.len",
    "table.getn",
}


ignore = {
    --"6.", -- ignore whitespace warnings
}


exclude_files = {
    -- The Github Actions Lua Environment
    ".lua",
    ".luarocks",
    ".install",
}

files["src/logging/nginx.lua"] = {
    std = "+ngx_lua"
}
