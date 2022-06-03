
require 'libinjection'

-- dofile('sqlifingerprints.lua')

-- silly callback that just calls back into C
-- identical to libinjection_is_sqli(sql_state, string_input, nil)
--
function check_pattern_c(sqlstate)
    return(libinjection.sqli_blacklist(sqlstate) and
            libinjection.sqli_not_whitelist(sqlstate))
end

-- half lua / half c checker
-- use lua based fingerprint lookup and still uses C code
-- to eliminate false positives
function check_pattern(sqlstate)
    fp = sqlstate.pat
    if sqlifingerprints[fp] == true then
        -- try to eliminate certain false positives
        return(libinjection.sqli_not_whitelist(sqlstate))
    else
        -- not sqli
        return 0
    end
end

function lookup_word(sqlstate, ltype, word)
   if ltype == 'X' then
       return words['0' .. word:upper()]
   else
       return words[word:upper()]
   end
end

dofile('words.lua')


-- THIS USES BUILT IN FINGERPRINTS
--  (with last arg of 'nil')
sqli = '1 union select * from table'


sql_state = libinjection.sqli_state()
libinjection.sqli_init(sql_state, sqli, sqli:len(), 0)

print(libinjection.is_sqli(sql_state))
print(sql_state.pat)
print('----')



inputs = {
     "123 LIKE -1234.5678E+2;",
     "APPLE 1   9.123 'FOO' \"BAR\"",
     "/* BAR */ UNION ALL SELECT (2,3,4)",
     "1 || COS(+0X04) --FOOBAR",
     "dog apple @cat banana bar",
     "dog apple cat \"banana \'bar",
     "102 TABLE CLOTH"
}

function benchmark(imax)
   local x,s
   local t0 = os.clock()
   local sql_state = libinjection.sqli_state()
   for x = 0, imax do
       s = inputs[(x % 7) + 1]
       libinjection.sqli_init(sql_state, s, s:len(), 0)
       libinjection.is_sqli(sql_state)
   end
   local t1 = os.clock()
   print( imax / (t1-t0) )
end

function benchmark_callback(imax)
   local x,s
   local t0 = os.clock()
   local sql_state = libinjection.sqli_state()
   for x = 0, imax do
       s = inputs[(x % 7) + 1]
       libinjection.sqli_init(sql_state, s, s:len(), 0)
       libinjection.sqli_callback(sql_state, 'lookup_word');
       libinjection.is_sqli(sql_state)
   end
   local t1 = os.clock()
   print( imax / (t1-t0) )
end

benchmark(1000000)
benchmark_callback(1000000)

-- THIS USES LUA FINGERPRINTS via 'check_pattern' function above

if 0 then
for x = 1,2 do
   ok = libinjection.is_sqli(sql_state)
   if ok == 1 then
      print(sql_state.pat)
      vec = sql_state.tokenvec
      for i = 1, sql_state.pat:len() do
         print(vec[i].type, vec[i].val)
      end
   end
end
end

