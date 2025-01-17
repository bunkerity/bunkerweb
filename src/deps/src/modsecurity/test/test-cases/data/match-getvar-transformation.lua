function main()
    ret = nil
    m.log(9, "Lets rock.");

    var = m.getvar("tx.test" , "lowercase");
    if var == nil then
        m.log(9, "Don't know what to say...");
        return ret;
    end

    if var == "FELIPE" then
        m.log(9, "Ops.");
    elseif var == "felipe" then
        m.log(9, "Just fine.");
        ret ="ok";
    else
        m.log(9, "Really?");
    end

    return "whee"
end
