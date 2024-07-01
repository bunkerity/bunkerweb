function main()
    ret = nil
    m.log(9, "Lets rock.");

    var = m.getvar("tx.test" , { "lowercase", "uppercase" });
    if var == nil then
        m.log(9, "Don't know what to say...");
        return ret;
    end

    if var == "FELIPE" then
        m.log(9, "Whee. Working like a charm. That is what we have: " .. var);
    elseif var == "felipe" then
        m.log(9, "Oh boy. Got: " .. var);
        ret ="ok";
    else
        m.log(9, "Really?");
    end

    return "whee"
end
