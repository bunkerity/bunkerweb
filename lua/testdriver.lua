require 'libinjection'
require 'Test.More'
require 'Test.Builder.Tester'

function trim(s)
    return s:find'^%s*$' and '' or s:match'^%s*(.*%S)'
end

function print_token_string(tok)
    local out = ''
    if tok.str_open ~= '\0' then
        out = out .. tok.str_open
    end
    out = out .. tok.val
    if tok.str_close ~= '\0' then
        out = out .. tok.str_close
    end
    return trim(out)
end

function print_token(tok)
   local out = ''
   out = out .. tok.type
   out = out .. ' '
   if tok.type == 's' then
       out = out .. print_token_string(tok)
   elseif tok.type == 'v' then
       if tok.count == 1 then
           out = out .. '@'
       elseif tok.count == 2 then
           out = out .. '@@'
       end
       out = out .. print_token_string(tok)
   else
       out = out .. tok.val
   end
   return '\n' .. trim(out)
end

function test_tokens(input)
    local out = ''
    local sql_state = libinjection.sqli_state()
    libinjection.sqli_init(sql_state, input, input:len(),
                           libinjection.FLAG_QUOTE_NONE + libinjection.FLAG_SQL_ANSI)
    while (libinjection.sqli_tokenize(sql_state) == 1) do
        out = out .. print_token(sql_state.current)
    end
    return out
end

function test_tokens_mysql(input)
    local out = ''
    local sql_state = libinjection.sqli_state()
    libinjection.sqli_init(sql_state, input, input:len(),
                           libinjection.FLAG_QUOTE_NONE +  libinjection.FLAG_SQL_MYSQL)
    while (libinjection.sqli_tokenize(sql_state) == 1) do
        out = out .. print_token(sql_state.current)
    end
    return out
end

function test_folding(input)
    local out = ''
    local sql_state = libinjection.sqli_state()
    libinjection.sqli_init(sql_state, input, input:len(), 0)
    libinjection.sqli_fingerprint(sql_state,
                     libinjection.FLAG_QUOTE_NONE + libinjection.FLAG_SQL_ANSI)
    for i = 1, sql_state.fingerprint:len() do
        -- c array is still 0 based
        out = out .. print_token(libinjection.sqli_get_token(sql_state, i-1))
    end
    -- hack for when there is no output
    if out == '' then
        out = '\n'
    end

    return out
end

function test_fingerprints(input)
    local out = ''
    local sql_state = libinjection.sqli_state()
    libinjection.sqli_init(sql_state, input, input:len(), 0)
    local issqli = libinjection.is_sqli(sql_state)
    if issqli == 1 then
        out = sql_state.fingerprint
    end
    return out
end

