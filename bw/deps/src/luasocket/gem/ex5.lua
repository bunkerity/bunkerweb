function source.empty(err)
  return function()
    return nil, err
  end
end

function source.file(handle, io_err)
  if handle then
    return function()
      local chunk = handle:read(20)
      if not chunk then handle:close() end
      return chunk
    end
  else return source.empty(io_err or "unable to open file") end
end
