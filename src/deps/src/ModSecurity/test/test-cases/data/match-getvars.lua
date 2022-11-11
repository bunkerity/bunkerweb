function dump(o)
   if type(o) == 'table' then
      local s = '{ '
      for k,v in pairs(o) do
         if type(k) ~= 'number' then k = '"'..k..'"' end
         s = s .. '['..k..'] = ' .. dump(v) .. ','
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
