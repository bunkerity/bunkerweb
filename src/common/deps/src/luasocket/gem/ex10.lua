function pump.step(src, snk)
  local chunk, src_err = src()
  local ret, snk_err = snk(chunk, src_err)
  if chunk and ret then return 1
  else return nil, src_err or snk_err end
end

function pump.all(src, snk, step)
    step = step or pump.step
    while true do
        local ret, err = step(src, snk)
        if not ret then
            if err then return nil, err
            else return 1 end
        end
    end
end
