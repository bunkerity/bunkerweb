local function chainpair(f1, f2)
  return function(chunk)
    local ret = f2(f1(chunk))
    if chunk then return ret
    else return (ret or "") .. (f2() or "") end
  end
end

function filter.chain(...)
  local f = select(1, ...) 
  for i = 2, select('#', ...) do
    f = chainpair(f, select(i, ...))
  end
  return f
end
