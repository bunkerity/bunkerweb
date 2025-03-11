local M = {}


M.HTTP_CODE = {}
M.HTTP_CODE["200"] = ngx.HTTP_OK
M.HTTP_CODE["202"] = ngx.HTTP_ACCEPTED
M.HTTP_CODE["204"] = ngx.HTTP_NO_CONTENT
M.HTTP_CODE["301"] = ngx.HTTP_MOVED_PERMANENTLY
M.HTTP_CODE["302"] = ngx.HTTP_MOVED_TEMPORARILY
M.HTTP_CODE["400"] = ngx.HTTP_BAD_REQUEST
M.HTTP_CODE["401"] = ngx.HTTP_UNAUTHORIZED
M.HTTP_CODE["401"] = ngx.HTTP_UNAUTHORIZED
M.HTTP_CODE["403"] = ngx.HTTP_FORBIDDEN
M.HTTP_CODE["404"] = ngx.HTTP_NOT_FOUND
M.HTTP_CODE["405"] = ngx.HTTP_NOT_ALLOWED
M.HTTP_CODE["406"] = ngx.HTTP_NOT_ACCEPTABLE
M.HTTP_CODE["444"] = ngx.HTTP_CLOSE
M.HTTP_CODE["500"] = ngx.HTTP_INTERNAL_SERVER_ERROR

function M.read_file(path)
   local file = io.open(path, "r") -- r read mode and b binary mode
   if not file then return nil end
   io.input(file)
   local content = io.read("*a")
   io.close(file)
   return content:sub(1,-2)
 end

function M.file_exist(path)
 if path == nil then
   return nil
 end
 local f = io.open(path, "r")
 if f ~= nil then
   io.close(f)
   return true
 else
   return false
 end
end

function M.starts_with(str, start)
    return str:sub(1, #start) == start
 end

 function M.ends_with(str, ending)
    return ending == "" or str:sub(-#ending) == ending
 end

function M.table_len(table)
   local count = 0
   for k, v in pairs(table) do
      count = count + 1
   end
   return count
end

return M
