local template = require "resty.template"

local ok, new_tab = pcall(require, "table.new")
if not ok then
    new_tab = function() return {} end
end

local function run(iterations)

    local gc, total, print, parse, compile, clock, format = collectgarbage, 0, ngx and ngx.say or print, template.parse,
                                                            template.compile, os.clock, string.format

    iterations = iterations or 1000

    local view = [[
    <ul>
    {% for _, v in ipairs(context) do %}
        <li>{{v}}</li>
    {% end %}
    </ul>]]

    print(format("Running %d iterations in each test", iterations))

    gc()
    gc()

    local x = clock()
    for _ = 1, iterations do
        parse(view, true)
    end
    local z = clock() - x
    print(format("    Parsing Time: %.6f", z))
    total = total + z

    gc()
    gc()

    x = clock()
    for _ = 1, iterations do
        compile(view, nil, true)
        template.cache = {}
    end
    z = clock() - x
    print(format("Compilation Time: %.6f (template)", z))
    total = total + z

    compile(view, nil, true)

    gc()
    gc()

    x = clock()
    for _ = 1, iterations do
        compile(view, 1, true)
    end
    z = clock() - x
    print(format("Compilation Time: %.6f (template, cached)", z))
    total = total + z

    local context = { "Emma", "James", "Nicholas", "Mary" }

    template.cache = {}

    gc()
    gc()

    x = clock()
    for _ = 1, iterations do
        compile(view, 1, true)(context)
        template.cache = {}
    end
    z = clock() - x
    print(format("  Execution Time: %.6f (same template)", z))
    total = total + z

    template.cache = {}
    compile(view, 1, true)

    gc()
    gc()

    x = clock()
    for _ = 1, iterations do
        compile(view, 1, true)(context)
    end
    z = clock() - x
    print(format("  Execution Time: %.6f (same template, cached)", z))
    total = total + z

    template.cache = {}

    local views = new_tab(iterations, 0)
    for i = 1, iterations do
        views[i] = "<h1>Iteration " .. i .. "</h1>\n" .. view
    end

    gc()
    gc()

    x = clock()
    for i = 1, iterations do
        compile(views[i], i, true)(context)
    end
    z = clock() - x
    print(format("  Execution Time: %.6f (different template)", z))
    total = total + z

    gc()
    gc()

    x = clock()
    for i = 1, iterations do
        compile(views[i], i, true)(context)
    end
    z = clock() - x
    print(format("  Execution Time: %.6f (different template, cached)", z))
    total = total + z

    local contexts = new_tab(iterations, 0)

    for i = 1, iterations do
        contexts[i] = { "Emma", "James", "Nicholas", "Mary" }
    end

    template.cache = {}

    gc()
    gc()

    x = clock()
    for i = 1, iterations do
        compile(views[i], i, true)(contexts[i])
    end
    z = clock() - x
    print(format("  Execution Time: %.6f (different template, different context)", z))
    total = total + z

    gc()
    gc()

    x = clock()
    for i = 1, iterations do
        compile(views[i], i, true)(contexts[i])
    end
    z = clock() - x
    print(format("  Execution Time: %.6f (different template, different context, cached)", z))
    total = total + z
    print(format("      Total Time: %.6f", total))
end

return {
    run = run
}
