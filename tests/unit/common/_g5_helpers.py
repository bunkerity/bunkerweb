"""Helpers of ``test_ignore_uri_normalized_path_regression.py``.

PCRE is not available in plain Lua, so ``PCRE_LUA`` is a stand-in for ``utils.regex_match`` that understands the one
construct the tests need beyond Lua patterns: a ``^/(?!word)`` negative lookahead. A backslash-escaped ``?`` becomes a
Lua ``%?``. Everything else is passed to ``string.find`` as is.
"""

PCRE_LUA = r"""
function pcre_match(subject, pattern)
    if subject == nil then return nil end
    local word = pattern:match("^%^/%(%?!(.-)%)$")
    if word then
        return (subject:sub(1, 1) == "/" and subject:sub(2, 1 + #word) ~= word) and true or nil
    end
    return subject:find((pattern:gsub("\\%?", "%%?"))) and true or nil
end
"""
