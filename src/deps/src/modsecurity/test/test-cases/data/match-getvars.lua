function dump(o)
   if type(o) == 'table' then
      local s = '{ '
      for k,v in pairs(o) do
         -- In Lua 5.5, generic-for loop variables (k and v) are read-only,
         -- so we copy k into a local before formatting. This works in earlier
         -- Lua versions too.
         local key_str = k
         if type(key_str) ~= 'number' then
            key_str = '"'..key_str..'"'
         end
         s = s .. '['..key_str..'] = ' .. dump(v) .. ','
      end
      return s .. '} '
   else
      return tostring(o)
   end
end

function main()
    ret = nil
    m.log(9, "Here I am");
    z = m.getvars("QUERY_STRING");
    m.log(9, "Z: " .. dump(z))

    return ret
end
