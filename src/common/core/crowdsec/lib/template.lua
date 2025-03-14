local template = {}

function template.compile(template_str, args)

    for k, v in pairs(args) do
        local var = "{{" .. k .. "}}"
        template_str = template_str:gsub(var, v)
    end

    return template_str
end

return template
