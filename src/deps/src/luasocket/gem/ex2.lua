function filter.cycle(lowlevel, context, extra)
  return function(chunk)
    local ret
    ret, context = lowlevel(context, chunk, extra)
    return ret
  end
end

function normalize(marker)
  return filter.cycle(eol, 0, marker)
end
