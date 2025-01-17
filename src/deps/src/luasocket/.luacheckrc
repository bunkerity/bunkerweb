unused_args     = false
redefined       = false
max_line_length = false

not_globals = {
    "string.len",
    "table.getn",
}

include_files = {
    "**/*.lua",
    "**/*.rockspec",
    ".busted",
    ".luacheckrc",
}

exclude_files = {
    "etc/*.lua",
    "etc/**/*.lua",
    "test/*.lua",
    "test/**/*.lua",
    "samples/*.lua",
    "samples/**/*.lua",
    "gem/*.lua",
    "gem/**/*.lua",
    -- GH Actions Lua Environment
    ".lua",
    ".luarocks",
    ".install",
}

