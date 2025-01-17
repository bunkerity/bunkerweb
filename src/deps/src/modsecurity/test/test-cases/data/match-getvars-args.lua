function main()
    local d = m.getvars("ARGS");
    local size = #d;
    m.log(9,"ARGS count read =" .. tostring(size));

    ret = nil

    if ( #d == 2 ) then
        return nil
    end

    return "Unexpected result"
end
