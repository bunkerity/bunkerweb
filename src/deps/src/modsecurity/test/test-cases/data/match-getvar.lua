function main()
    ret = nil

    num = m.getvar("tx.test");
    if num == nil then
        m.log(9, "Don't know what to say about this so called number.");
        return ret
    end
    num = tonumber(num)

    if num > 1 then
        m.log(9, "Number is bigger than one.");
        ret = "Whee :)"
    else
        m.log(9, "Really?");
    end

    return ret
end
