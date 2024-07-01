-- Your script must define the main entry
-- point, as below.
function main()
    -- Log something at level 1. Normally you shouldn't be
    -- logging anything, especially not at level 1, but this is
    -- just to show you can. Useful for debugging.
    m.log(1, "Hello world!");

    -- Retrieve one variable.
    local var1 = m.getvar("REMOTE_ADDR");

    -- Retrieve one variable, applying one transformation function.
    -- The second parameter is a string.
    local var2 = m.getvar("ARGS", "lowercase");

    -- Retrieve one variable, applying several transformation functions.
    -- The second parameter is now a list. You should note that m.getvar()
    -- requires the use of comma to separate collection names from
    -- variable names. This is because only one variable is returned.
    local var3 = m.getvar("ARGS.p", { "lowercase", "compressWhitespace" } );

    -- If you want this rule to match return a string
    -- containing the error message. The message must contain the name
    -- of the variable where the problem is located.
    -- return "Variable ARGS:p looks suspicious!"

    -- Otherwise, simply return nil.
    return nil;
end