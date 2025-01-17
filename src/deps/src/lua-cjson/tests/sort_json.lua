-- NOTE: This will only work for simple tests. It doesn't parse strings so if
-- you put any symbols like {?[], inside of a string literal then it will break
-- The point of this function is to test basic structures, and not test JSON
-- strings

local function sort_callback(str)
  local inside = str:sub(2, -2)

  local parts = {}
  local buffer = ""
  local pos = 1

  while true do
    if pos > #inside then
      break
    end

    local append

    local parens = inside:match("^%b{}", pos)
    if parens then
      pos = pos + #parens
      append = sort_callback(parens)
    else
      local array = inside:match("^%b[]", pos)
      if array then
        pos = pos + #array
        append = array
      else
        local front = inside:sub(pos, pos)
        pos = pos + 1

        if front == "," then
          table.insert(parts, buffer)
          buffer = ""
        else
          append = front
        end
      end
    end

    if append then
      buffer = buffer .. append
    end
  end

  if buffer ~= "" then
    table.insert(parts, buffer)
  end

  table.sort(parts)

  return "{" .. table.concat(parts, ",") .. "}"
end

local function sort_json(str)
  return (str:gsub("%b{}", sort_callback))
end


return sort_json
