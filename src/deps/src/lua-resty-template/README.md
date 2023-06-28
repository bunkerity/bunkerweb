# lua-resty-template

**lua-resty-template** is a compiling (1) (HTML) templating engine for Lua and OpenResty.

(1) with compilation we mean that templates are translated to Lua functions that you may call or `string.dump`
as a binary bytecode blobs to disk that can be later utilized with `lua-resty-template` or basic `load` and
`loadfile` standard Lua functions (see also [Template Precompilation](#template-precompilation)). Although,
generally you don't need to do that as `lua-resty-template` handles this behind the scenes.


## Hello World with lua-resty-template

```lua
local template = require "resty.template"      -- OR
local template = require "resty.template.safe" -- return nil, err on errors

-- Using template.new
local view = template.new "view.html"
view.message = "Hello, World!"
view:render()
-- Using template.render
template.render("view.html", { message = "Hello, World!" })
```


##### view.html
```html
<!DOCTYPE html>
<html>
<body>
  <h1>{{message}}</h1>
</body>
</html>
```


##### Output
```html
<!DOCTYPE html>
<html>
<body>
  <h1>Hello, World!</h1>
</body>
</html>
```

The same can be done with inline template string:

```lua
-- Using template string
template.render([[
<!DOCTYPE html>
<html>
<body>
  <h1>{{message}}</h1>
</body>
</html>]], { message = "Hello, World!" })
```


## Contents

- [Template Syntax](#template-syntax)
  - [Example](#example)
  - [Reserved Context Keys and Remarks](#reserved-context-keys-and-remarks)
- [Installation](#installation)
  - [Using OpenResty Package Manager (opm)](#using-openresty-package-manager-opm)
  - [Using LuaRocks](#using-luarocks)
- [Nginx / OpenResty Configuration](#nginx--openresty-configuration)
- [Lua API](#lua-api)
  - [template.root](#templateroot)
  - [template.location](#templatelocation)
  - [table template.new(view, layout)](#table-templatenewview-layout)
  - [boolean template.caching(boolean or nil)](#boolean-templatecachingboolean-or-nil)
  - [function, boolean template.compile(view, cache_key, plain)](#function-boolean-templatecompileview-cache_key-plain)
  - [function, boolean template.compile_string(view, cache_key)](#function-boolean-templatecompile_stringview-cache_key)
  - [function, boolean template.compile_file(view, cache_key)](#function-boolean-templatecompile_fileview-cache_key)
  - [template.visit(func)](#templatevisitfunc)
  - [string template.process(view, context, cache_key, plain)](#string-templateprocessview-context-cache_key-plain)
  - [string template.process_string(view, context, cache_key)](#string-templateprocess_stringview-context-cache_key)
  - [string template.process_file(view, context, cache_key)](#string-templateprocess_fileview-context-cache_key)  
  - [template.render(view, context, cache_key, plain)](#templaterenderview-context-cache_key-plain)
  - [template.render_string(view, context, cache_key)](#templaterender_stringview-context-cache_key)
  - [template.render_file(view, context, cache_key)](#templaterender_fileview-context-cache_key)
  - [string template.parse(view, plain)](#string-templateparseview-plain)
  - [string template.parse_string(view, plain)](#string-templateparse_stringview-plain)
  - [string template.parse_file(view, plain)](#string-templateparse_fileview-plain)
  - [string template.precompile(view, path, strip)](#string-templateprecompileview-path-strip)
  - [string template.precompile_string(view, path, strip)](#string-templateprecompile_stringview-path-strip)
  - [string template.precompile_file(view, path, strip)](#string-templateprecompile_fileview-path-strip)  
  - [string template.load(view, plain)](#string-templateloadview-plain)
  - [string template.load_string(view)](#string-templateload_stringview)
  - [string template.load_file(view)](#string-templateload_fileview)
  - [template.print](#templateprint)
- [Template Precompilation](#template-precompilation)
- [Template Helpers](#template-helpers)
  - [Built-in Helpers](#built-in-helpers)
    - [echo(...)](#echo)
    - [include(view, context)](#includeview-context)
  - [Other Ways to Extend](#other-ways-to-extend)
- [Usage Examples](#usage-examples)
   - [Template Including](#template-including)
   - [Views with Layouts](#views-with-layouts)
   - [Using Blocks](#using-blocks)
   - [Grandfather-Father-Son Inheritance](#grandfather-father-son-inheritance)
   - [Macros](#macros)
   - [Calling Methods in Templates](#calling-methods-in-templates)
   - [Embedding Angular or other tags / templating inside the Templates](#embedding-angular-or-other-tags--templating-inside-the-templates)
   - [Embedding Markdown inside the Templates](#embedding-markdown-inside-the-templates)
   - [Lua Server Pages (LSP) with OpenResty](#lua-server-pages-lsp-with-openresty)
- [FAQ](#faq)
- [Alternatives](#alternatives)
- [Benchmarks](#benchmarks)
- [Changes](#changes)
- [Roadmap](#roadmap)
- [See Also](#see-also)
- [License](#license)


## Template Syntax

You may use the following tags in templates:

* `{{expression}}`, writes result of expression - html escaped
* `{*expression*}`, writes result of expression 
* `{% lua code %}`, executes Lua code
* `{(template)}`, includes `template` file, you may also supply context for include file `{(file.html, { message = "Hello, World" } )}` (NOTE: you cannot use comma (`,`) in `file.html`, in that case use `{["file,with,comma"]}` instead)
* `{[expression]}`, includes `expression` file (the result of expression), you may also supply context for include file `{["file.html", { message = "Hello, World" } ]}`
* `{-block-}...{-block-}`, wraps inside of a `{-block-}` to a value stored in a `blocks` table with a key `block` (in this case), see [using blocks](https://github.com/bungle/lua-resty-template#using-blocks). Don't use predefined block names `verbatim` and `raw`.
* `{-verbatim-}...{-verbatim-}` and `{-raw-}...{-raw-}` are predefined blocks whose inside is not processed by the `lua-resty-template` but the content is outputted as is.
* `{# comments #}` everything between `{#` and `#}` is considered to be commented out (i.e. not outputted or executed)

From templates you may access everything in `context` table, and everything in `template` table.
In templates you can also access `context` and `template` by prefixing keys.

```html
<h1>{{message}}</h1> == <h1>{{context.message}}</h1>
```


##### Short Escaping Syntax

If you don't want a particular template tag to be processed you may escape the starting tag with backslash `\`:

```html
<h1>\{{message}}</h1>
```

This will output (instead of evaluating the message):

```html
<h1>{{message}}</h1>
```

If you want to add backslash char just before template tag, you need to escape that as well:

```html
<h1>\\{{message}}</h1>
```

This will output:

```html
<h1>\[message-variables-content-here]</h1>
```


##### A Word About Complex Keys in Context Table

Say you have this kind of a context table:

```lua
local ctx = {["foo:bar"] = "foobar"}
```

And you want to render the `ctx["foo:bar"]`'s value `foobar` in your template.  You have to specify it explicitly
by referencing the `context` in your template:

```html
{# {*["foo:bar"]*} won't work, you need to use: #}
{*context["foo:bar"]*}
```

Or altogether:

```lua
template.render([[
{*context["foo:bar"]*}
]], {["foo:bar"] = "foobar"})
```


##### A Word About HTML Escaping

Only strings are escaped, functions are called without arguments (recursively) and results are returned as is,
other types are `tostring`ified. `nil`s and `ngx.null`s are converted to empty strings `""`.

Escaped HTML characters:

* `&` becomes `&amp;`
* `<` becomes `&lt;`
* `>` becomes `&gt;`
* `"` becomes `&quot;`
* `'` becomes `&#39;`
* `/` becomes `&#47;`


#### Example

##### Lua
```lua
local template = require "resty.template"
template.render("view.html", {
  title   = "Testing lua-resty-template",
  message = "Hello, World!",
  names   = { "James", "Jack", "Anne" },
  jquery  = '<script src="js/jquery.min.js"></script>' 
})
```


##### view.html
```html
{(header.html)}
<h1>{{message}}</h1>
<ul>
{% for _, name in ipairs(names) do %}
    <li>{{name}}</li>
{% end %}
</ul>
{(footer.html)}
```


##### header.html
```html
<!DOCTYPE html>
<html>
<head>
  <title>{{title}}</title>
  {*jquery*}
</head>
<body>
```


##### footer.html
```html
</body>
</html>
```


#### Reserved Context Keys and Remarks

It is advised that you do not use these keys in your context tables:

* `___`, holds the compiled template, if set you need to use `{{context.___}}`
* `context`, holds the current context, if set you need to use `{{context.context}}`
* `echo`, holds the echo helper function, if set you need to use `{{context.echo}}`
* `include`, holds the include helper function, if set you need to use `{{context.include}}`
* `layout`, holds the layout by which the view will be decorated, if set you need to use `{{context.layout}}`
* `blocks`, holds the blocks, if set you need to use `{{context.blocks}}` (see: [using blocks](#using-blocks))
* `template`, holds the template table, if set you need to use `{{context.template}}`

In addition to that with `template.new` you should not overwrite:

* `render`, the function that renders a view, obviously ;-)

You should also not `{(view.html)}` recursively:


##### Lua
```lua
template.render "view.html"
```


##### view.html
```html
{(view.html)}
```

You can  load templates from "sub-directories" as well with `{(syntax)}`:


##### view.html
```html
{(users/list.html)}
```

**Also note that you can provide template either as a file path or as a string. If the file exists,
it will be used, otherwise the string is used. See also [`template.load`](#templateload).**


## Installation

Just place [`template.lua`](https://github.com/bungle/lua-resty-template/blob/master/lib/resty/template.lua) and
[`template`](https://github.com/bungle/lua-resty-template/tree/master/lib/resty/template) directory somewhere in
your `package.path`, under `resty` directory. If you are using OpenResty, the default location would
be `/usr/local/openresty/lualib/resty`.


### Using OpenResty Package Manager (opm)

```Shell
$ opm get bungle/lua-resty-template
```


### Using LuaRocks

```Shell
$ luarocks install lua-resty-template
```

LuaRocks repository for `lua-resty-template` is located at https://luarocks.org/modules/bungle/lua-resty-template.


## Nginx / OpenResty Configuration

When `lua-resty-template` is used in context of Nginx / OpenResty there are a few configuration directives
that you need to be aware:

* `template_root` (`set $template_root /var/www/site/templates`)
* `template_location` (`set $template_location /templates`)

If none of these are set in Nginx configuration, `ngx.var.document_root` (aka root-directive) value is used.
If `template_location` is set, it will be used first, and if the location returns anything but `200` as
a status code, we do fallback to either `template_root` (if defined) or `document_root`.

With `lua-resty-template` `2.0` it is possible to override `$template_root` and `$template_location` with
`Lua` code:

```lua
local template = require "resty.template".new({
  root     = "/templates",
  location = "/templates" 
})
```


##### Using `document_root`

This one tries to load file content with Lua code from `html` directory (relative to Nginx prefix).

```nginx
http {
  server {
    location / {
      root html;
      content_by_lua '
        local template = require "resty.template"
        template.render("view.html", { message = "Hello, World!" })
      ';      
    }
  }
}
```


##### Using `template_root`

This one tries to load file content with Lua code from `/usr/local/openresty/nginx/html/templates` directory.

```nginx
http {
  server {
    set $template_root /usr/local/openresty/nginx/html/templates;
    location / {
      root html;
      content_by_lua '
        local template = require "resty.template"
        template.render("view.html", { message = "Hello, World!" })
      ';      
    }
  }
}
```


##### Using `template_location`

This one tries to load content with `ngx.location.capture` from `/templates` location (in this case this is
served with `ngx_static` module).

```nginx
http {
  server {
    set $template_location /templates;
    location / {
      root html;
      content_by_lua '
        local template = require "resty.template"
        template.render("view.html", { message = "Hello, World!" })
      ';      
    }
    location /templates {
      internal;
      alias html/templates/;
    }    
  }
}
```

**See also [`template.load`](#templateload).**


## Lua API

#### template.root

You can setup template root by setting this variable which will be looked for template files:

```lua
local template = require "resty.template".new({
  root = "/templates"
})
template.render_file("test.html")
```

This property overrides the one set in Nginx configuration (`set $template_root /my-templates;`)


#### template.location

This is what you can use with OpenResty as that will use `ngx.location.capture` to fetch templates
files in non-blocking fashion.

```lua
local template = require "resty.template".new({
  location = "/templates"
})
template.render_file("test.html")
```

This property overrides the one set in Nginx configuration (`set $template_location /my-templates;`)


#### table template.new(view, layout)

Creates a new template instance that is used as a (default) context when `render`ed. A table that gets created has
only one method `render`, but the table also has metatable with `__tostring` defined. See the example below. Both
`view` and `layout` arguments can either be strings or file paths, but layout can also be a table created previously
with `template.new`.

With 2.0 the new can also be used without arguments, which creates a new template instance:

```lua
local template = require "resty.template".new()
```

You can also pass a table that is then modified to be a template:

```lua
local config = {
  root = "/templates"
}

local template = require "resty.template".new(config)
```

This is handy as the `template` created by `new` does not share the cache with the global template returned
by `require "resty.template"` (this was reported with issue [#25](https://github.com/bungle/lua-resty-template/issues/25)).

You can also pass a boolean `true` or `false` as a `view` parameter which means that either `safe` or `un-safe`
version of template is returned:

```lua
local unsafe = require "resty.template"
local safe   = unsafe.new(true)
```

There is also a default `safe` implementation available:

```lua
local safe = require "resty.template.safe"
-- you can create instance of safe too:
local safe_instance = safe.new()
```

`safe` version uses `return nil, err` Lua error handling pattern and `unsafe` just throws the errors, which you
can catch with `pcall`, `xpcall` or `coroutine.wrap`.


Here are examples of using `new` with arguments:

```lua
local view = template.new"template.html"              -- or
local view = template.new("view.html", "layout.html") -- or
local view = template.new[[<h1>{{message}}</h1>]]     -- or
local view = template.new([[<h1>{{message}}</h1>]], [[
<html>
<body>
  {*view*}
</body>
</html>
]])
```


##### Example
```lua
local template = require "resty.template"
local view = template.new"view.html"
view.message  = "Hello, World!"
view:render()
-- You may also replace context on render
view:render{ title = "Testing lua-resty-template" }
-- If you want to include view context in  replacement context
view:render(setmetatable({ title = "Testing lua-resty-template" }, { __index = view }))
-- To get rendered template as a string, you can use tostring
local result = tostring(view)
```


#### boolean template.caching(boolean or nil)

This function enables or disables template caching, or if no parameters are passed, returns current state of
template caching. By default template caching is enabled, but you may want to disable it on development or
low-memory situations.

```lua
local template = require "resty.template"   
-- Get current state of template caching
local enabled = template.caching()
-- Disable template caching
template.caching(false)
-- Enable template caching
template.caching(true)
```

Please note that if the template was already cached when compiling a template, the cached version will be returned.
You may want to flush cache with `template.cache = {}` to ensure that your template really gets recompiled.


#### function, boolean template.compile(view, cache_key, plain)

Parses, compiles and caches (if caching is enabled) a template and returns the compiled template as a function
that takes context as a parameter and returns rendered template as a string. Optionally you may pass `cache_key` that
is used as a cache key. If cache key is not provided `view` wil be used as a cache key. If cache key is `no-cache`
the template cache will not be checked and the resulting function will not be cached. You may also optionally
pass `plain` with a value of `true` if the `view` is plain text string (this will skip `template.load` and binary
chunk detection in `template.parse` phase). If `plain` is `false` the template is considered to be a file,
and all the issues with file reading are considered as errors. If the `plain` is set to `nil` (the default)
the template does not consider file reading errors as fatal, and returns back the `view` (usually the path of
the template).

```lua
local func = template.compile("template.html")          -- or
local func = template.compile([[<h1>{{message}}</h1>]])
```


##### Example

```lua
local template = require "resty.template"
local func     = template.compile("view.html")
local world    = func{ message = "Hello, World!" }
local universe = func{ message = "Hello, Universe!" }
print(world, universe)
```

Also note the second return value which is a boolean. You may discard it, or use it to determine if
the returned function was cached.


#### function, boolean template.compile_string(view, cache_key)

This just calls `template.compile(view, cache_key, true)`


#### function, boolean template.compile_file(view, cache_key)

This just calls `template.compile(view, cache_key, false)`


#### template.visit(func)

Allows you to register template parser visitor functions. Visitors are called in the order they
are registered. And once registered, cannot be removed from parser. Perhaps it is easier to show
how it works:

```lua
local template = require "resty.template.safe".new()

local i = 0

template.visit(function(content, type, name)
  local trimmed = content:gsub("^%s+", ""):gsub("%s+$", "")
  if trimmed == "" then return content end
  i = i + 1
  print("  visit: ", i)
  if type then print("   type: ", type) end
  if name then print("   name: ", name) end
  print("content: ", trimmed)
  print()
  return content
end)

local func = template.compile([[
How are you, {{user.name}}?

Here is a new cooking recipe for you!

{% for i, ingredient in ipairs(ingredients) do %}
  {*i*}. {{ingredient}}
{% end %}
{-ad-}`lua-resty-template` the templating engine for OpenResty!{-ad-}
]])

local content = func{
  user = {
    name = "bungle"
  },
  ingredients = {
    "potatoes",
    "sausages"
  }
}

print(content)
```

This will output the following:

```
  visit: 1
content: How are you,

  visit: 2
   type: {
content: user.name

  visit: 3
content: ?

Here is a new cooking recipe for you!

  visit: 4
   type: %
content: for i, ingredient in ipairs(ingredients) do

  visit: 5
   type: *
content: i

  visit: 6
content: .

  visit: 7
   type: {
content: ingredient

  visit: 8
   type: %
content: end

  visit: 9
   type: -
   name: ad
content: `lua-resty-template` the templating engine for OpenResty!

  visit: 10
content: `lua-resty-template` the templating engine for OpenResty!

How are you, bungle?

Here is a new cooking recipe for you!

  1. potatoes
  2. sausages
```

The visitor functions should have this signature:
```
string function(content, type, name)
```

If the function doesn't modify the `content` it should return the `content` back, like the visitor
above does.

Here is a bit more advanced visitor example that handles run-time errors on expressions:

```lua
local template = require "resty.template".new()

template.render "Calculation: {{i*10}}"
```

This will runtime error with:
```
ERROR: [string "context=... or {}..."]:7: attempt to perform arithmetic on global 'i' (a nil value)
stack traceback:
	resty/template.lua:652: in function 'render'
	a.lua:52: in function 'file_gen'
	init_worker_by_lua:45: in function <init_worker_by_lua:43>
	[C]: in function 'xpcall'
	init_worker_by_lua:52: in function <init_worker_by_lua:50>
```

Now let's add a visitor that handles this error:

```lua
local template = require "resty.template".new()

template.visit(function(content, type)
  if type == "*" or type == "{" then
    return "select(3, pcall(function() return nil, " .. content .. " end)) or ''"
  end

  return content
end)

template.render "Calculation: {{i*10}}\n"
template.render("Calculation: {{i*10}}\n", { i = 1 })
```

This will output:

```
Calculation: 
Calculation: 10
```


#### string template.process(view, context, cache_key, plain)

Parses, compiles, caches (if caching is enabled) and returns output as string. You may optionally also
pass `cache_key` that is used as a cache key. If `plain` evaluates to `true`, the `view` is considered
to be plain string template (`template.load` and binary chunk detection is skipped on `template.parse`).
If `plain` is `false"` the template is considered to be a file, and all the issues with file reading are
considered as errors. If the `plain` is set to `nil` (the default) the template does not consider file
reading errors as fatal, and returns back the `view`.

```lua
local output = template.process("template.html", { message = "Hello, World!" })          -- or
local output = template.process([[<h1>{{message}}</h1>]], { message = "Hello, World!" })
```

#### string template.process_string(view, context, cache_key)

This just calls `template.process(view, context, cache_key, true)`


#### string template.process_file(view, context, cache_key)

This just calls `template.process(view, context, cache_key, false)`


#### template.render(view, context, cache_key, plain)

Parses, compiles, caches (if caching is enabled) and outputs template either with `ngx.print` if available,
or `print`. You may optionally also pass `cache_key` that is used as a cache key. If `plain` evaluates to
`true`, the `view` is considered to be plain string template (`template.load` and binary chunk detection
is skipped on `template.parse`). If `plain` is `false"` the template is considered to be a file, and
all the issues with file reading are considered as errors. If the `plain` is set to `nil` (the default)
the template does not consider file reading errors as fatal, and returns back the `view`.

```lua
template.render("template.html", { message = "Hello, World!" })          -- or
template.render([[<h1>{{message}}</h1>]], { message = "Hello, World!" })
```


#### template.render_string(view, context, cache_key)

This just calls `template.render(view, context, cache_key, true)`


#### template.render_file(view, context, cache_key)

This just calls `template.render(view, context, cache_key, false)`


#### string template.parse(view, plain)

Parses template file or string, and generates a parsed template string. This may come useful when debugging
templates. You should note that if you are trying to parse a binary chunk (e.g. one returned with
`template.compile`), `template.parse` will return that binary chunk as is. If `plain` evaluates to
`true`, the `view` is considered to be plain string template (`template.load` and binary chunk detection
is skipped on `template.parse`). If `plain` is `false"` the template is considered to be a file, and
all the issues with file reading are considered as errors. If the `plain` is set to `nil` (the default)
the template does not consider file reading errors as fatal, and returns back the `view`.

```lua
local t1 = template.parse("template.html")
local t2 = template.parse([[<h1>{{message}}</h1>]])
```


#### string template.parse_string(view, plain)

This just calls `template.parse(view, plain, true)`


#### string template.parse_file(view, plain)

This just calls `template.parse(view, plain, false)`


#### string template.precompile(view, path, strip, plain)

Precompiles template as a binary chunk. This binary chunk can be written out as a file (and you may use it
directly with Lua's `load` and `loadfile`). For convenience you may optionally specify `path` argument to
output binary chunk to file. You may also supply `strip` parameter with value of `false` to make precompiled
templates to have debug information as well (defaults to `true`). The last parameter `plain` means that
should complilation treat the `view` as `string` (`plain = true`) or as `file path` (`plain = false`) or
try first as a file, and fallback to `string` (`plain = nil`). In case the `plain=false` (a file) and there
is error with `file io` the function will also error with an assertion failure. 

```lua
local view = [[
<h1>{{title}}</h1>
<ul>
{% for _, v in ipairs(context) do %}
    <li>{{v}}</li>
{% end %}
</ul>]]

local compiled = template.precompile(view)

local file = io.open("precompiled-bin.html", "wb")
file:write(compiled)
file:close()

-- Alternatively you could just write (which does the same thing as above)
template.precompile(view, "precompiled-bin.html")

template.render("precompiled-bin.html", {
    title = "Names",
    "Emma", "James", "Nicholas", "Mary"
})
```


#### string template.precompile_string(view, path, strip)

This just calls `template.precompile(view, path, strip, true)`.


#### string template.precompile_file(view, path, strip)

This just calls `template.precompile(view, path, strip, false)`.


#### string template.load(view, plain)

This field is used to load templates. `template.parse` calls this function before it starts parsing the template
(assuming that optional `plain` argument in `template.parse` evaluates to `false` or `nil` (the default).
By default there are two loaders in `lua-resty-template`: one for Lua and the other for Nginx / OpenResty.
Users can overwrite this field with their own function. For example you may want to write a template loader
function that loads templates from a database.

The default `template.load` for Lua (attached as template.load when used directly with Lua):

```lua
function(view, plain)
    if plain == true then return view end
    local path, root = view, template.root
    if root and root ~= EMPTY then
        if byte(root, -1) == SOL then root = sub(root, 1, -2) end
        if byte(view,  1) == SOL then path = sub(view, 2) end
        path = root .. "/" .. path
    end
    return plain == false and assert(read_file(path)) or read_file(path) or view
end
```

The default `template.load` for Nginx / OpenResty (attached as template.load when used in context
of Nginx / OpenResty):

```lua
function(view, plain)
    if plain == true then return view end
    local vars = VAR_PHASES[phase()]
    local path = view
    local root = template.location
    if (not root or root == EMPTY) and vars then
        root = var.template_location
    end
    if root and root ~= EMPTY then
        if byte(root, -1) == SOL then root = sub(root, 1, -2) end
        if byte(path,  1) == SOL then path = sub(path, 2) end
        path = root .. "/" .. path
        local res = capture(path)
        if res.status == 200 then return res.body end
    end
    path = view
    root = template.root
    if (not root or root == EMPTY) and vars then
        root = var.template_root
        if not root or root == EMPTY then root = var.document_root or prefix end
    end
    if root and root ~= EMPTY then
        if byte(root, -1) == SOL then root = sub(root, 1, -2) end
        if byte(path,  1) == SOL then path = sub(path, 2) end
        path = root .. "/" .. path
    end
    return plain == false and assert(read_file(path)) or read_file(path) or view
end
```

As you can see, `lua-resty-template` always tries (by default) to load a template from a file
(or with `ngx.location.capture`) even if you provided template as a string. `lua-resty-template`.
But if you know that your templates are always strings, and not file paths, you may use `plain`
argument in `template.compile`, `template.render`, and `template.parse` OR replace `template.load`
with the simplest possible template loader there is (but be aware that if your templates use
`{(file.html)}` includes, those are considered as strings too, in this case `file.html` will
be the template string that is parsed) - you could also setup a loader that finds templates in
some database system, e.g. Redis:

```lua
local template = require "resty.template"
template.load = function(view, plain) return view end
```

If the `plain` parameter is `false` (`nil` is not treated as `false`), all the issues with file
io are considered assertion errors.


#### string template.load_string(view)

This just calls `template.load(view, true)`


#### string template.load_file(view)

This just calls `template.load(view, false)`


#### template.print

This field contains a function that is used on `template.render()` or
`template.new("example.html"):render()` to output the results. By default this holds either
`ngx.print` (if available) or `print`. You may want to (and are allowed to) overwrite this
field, if you want to use your own output function instead. This is also useful if you are
using some other framework, e.g. Turbo.lua (http://turbolua.org/).

```lua
local template = require "resty.template"

template.print = function(s)
  print(s)
  print("<!-- Output by My Function -->")
end
```


## Template Precompilation

`lua-resty-template` supports template precompilation. This can be useful when you want to
skip template parsing (and Lua interpretation) in production or if you do not want your
templates distributed as plain text files on production servers. Also by precompiling,
you can ensure that your templates do not contain something, that cannot be compiled
(they are syntactically valid Lua). Although templates are cached (even without precompilation),
there are some performance (and memory) gains. You could integrate template precompilation in
your build (or deployment) scripts (maybe as Gulp, Grunt or Ant tasks).


##### Precompiling template, and output it as a binary file

```lua
local template = require "resty.template"
local compiled = template.precompile("example.html", "example-bin.html")
```


##### Load precompiled template file, and run it with context parameters

```lua
local template = require "resty.template"
template.render("example-bin.html", { "Jack", "Mary" })
```


## Template Helpers

### Built-in Helpers

#### echo(...)

Echoes output. This is useful with `{% .. %}`:

```lua
require "resty.template".render[[
begin
{%
for i=1, 10 do
  echo("\tline: ", i, "\n")
end
%}
end
]]
```

This will output:

```
begin
	line: 1
	line: 2
	line: 3
	line: 4
	line: 5
	line: 6
	line: 7
	line: 8
	line: 9
	line: 10
end
```

This can also be written as but `echo` might come handy in some cases:

```lua
require "resty.template".render[[
begin
{% for i=1, 10 do %}
  line: {* i *}
{% end %}
end
]]
```


#### include(view, context)

This is mainly used with internally with `{(view.hmtl)}`, `{["view.hmtl"]}` and
with blocks `{-block-name-}..{-block-name-}`. If `context` is not given the context
used to compile parent view is used. This function will compile the `view` and call
the resulting function with `context` (or the `context` of parent view if not given).


### Other Ways to Extend

While `lua-resty-template` does not have much infrastucture or ways to extend it,
you still have a few possibilities that you may try.

* Adding methods to global `string`, and `table` types (not encouraged, though)
* Wrap your values with something before adding them in context (e.g. proxy-table)
* Create global functions
* Add local functions either to `template` table or `context` table
* Use metamethods in your tables

While modifying global types seems convenient, it can have nasty side effects.
That's why I suggest you to look at these libraries, and articles first:

* Method Chaining Wrapper (http://lua-users.org/wiki/MethodChainingWrapper)
* Moses (https://github.com/Yonaba/Moses)
* underscore-lua (https://github.com/jtarchie/underscore-lua)

You could for example add Moses' or Underscore's `_` to template table or context table.


##### Example

```lua
local _ = require "moses"
local template = require "resty.template"
template._ = _
```

Then you can use `_` inside your templates. I created one example template helper
that can be found from here:
https://github.com/bungle/lua-resty-template/blob/master/lib/resty/template/html.lua


##### Lua

```lua
local template = require "resty.template"
local html = require "resty.template.html"

template.render([[
<ul>
{% for _, person in ipairs(context) do %}
    {*html.li(person.name)*}
{% end %}
</ul>
<table>
{% for _, person in ipairs(context) do %}
    <tr data-sort="{{(person.name or ""):lower()}}">
        {*html.td{ id = person.id }(person.name)*}
    </tr>
{% end %}
</table>]], {
    { id = 1, name = "Emma"},
    { id = 2, name = "James" },
    { id = 3, name = "Nicholas" },
    { id = 4 }
})
```


##### Output

```html
<ul>
    <li>Emma</li>
    <li>James</li>
    <li>Nicholas</li>
    <li />
</ul>
<table>
    <tr data-sort="emma">
        <td id="1">Emma</td>
    </tr>
    <tr data-sort="james">
        <td id="2">James</td>
    </tr>
    <tr data-sort="nicholas">
        <td id="3">Nicholas</td>
    </tr>
    <tr data-sort="">
        <td id="4" />
    </tr>
</table>
```


## Usage Examples

### Template Including

You may include templates inside templates with `{(template)}` and `{(template, context)}` syntax.
The first one uses the current context as a context for included template, and the second one replaces
it with a new context. Here is example of using includes and passing a different context to include file:


##### Lua

```lua
local template = require "resty.template"
template.render("include.html", { users = {
    { name = "Jane", age = 29 },
    { name = "John", age = 25 }
}})
```

##### include.html

```html
<html>
<body>
<ul>
{% for _, user in ipairs(users) do %}
    {(user.html, user)}
{% end %}
</ul>
</body>
</html>
```

##### user.html

```html
<li>User {{name}} is of age {{age}}</li>
```

##### Outut

```html
<html>
<body>
<ul>
    <li>User Jane is of age 29</li>
    <li>User John is of age 25</li>
</ul>
</body>
</html>
```


### Views with Layouts

Layouts (or Master Pages) can be used to wrap a view inside another view (aka layout).


##### Lua

```lua
local template = require "resty.template"
local layout   = template.new "layout.html"
layout.title   = "Testing lua-resty-template"
layout.view    = template.compile "view.html" { message = "Hello, World!" }
layout:render()
-- Or like this
template.render("layout.html", {
  title = "Testing lua-resty-template",
  view  = template.compile "view.html" { message = "Hello, World!" }
})
-- Or maybe you like this style more
-- (but please remember that context.view is overwritten on rendering the layout.html)
local view     = template.new("view.html", "layout.html")
view.title     = "Testing lua-resty-template"
view.message   = "Hello, World!"
view:render()
-- Well, maybe like this then?
local layout   = template.new "layout.html"
layout.title   = "Testing lua-resty-template"
local view     = template.new("view.html", layout)
view.message   = "Hello, World!"
view:render()
```


##### view.html

```html
<h1>{{message}}</h1>
```

##### layout.html
```html
<!DOCTYPE html>
<html>
<head>
    <title>{{title}}</title>
</head>
<body>
    {*view*}
</body>
</html>
```


##### Alternatively you can define the layout in a view as well:

##### Lua

```lua
local view     = template.new("view.html", "layout.html")
view.title     = "Testing lua-resty-template"
view.message   = "Hello, World!"
view:render()
```


##### view.html

```html
{% layout="section.html" %}
<h1>{{message}}</h1>
```


##### section.html

```html
<div id="section">
    {*view*}
</div>
```


##### layout.html

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{title}}</title>
</head>
<body>
    {*view*}
</body>
</html>
```


##### Output

```html
<!DOCTYPE html>
<html>
<head>
    <title>Testing lua-resty-template</title>
</head>
<body>
<div id="section">
    <h1>Hello, World!</h1>
</div>
</body>
</html>
```


### Using Blocks

Blocks can be used to move different parts of the views to specific places in layouts. Layouts have placeholders
for blocks.


##### Lua

```lua
local view     = template.new("view.html", "layout.html")
view.title     = "Testing lua-resty-template blocks"
view.message   = "Hello, World!"
view.keywords  = { "test", "lua", "template", "blocks" }
view:render()
```


##### view.html

```html
<h1>{{message}}</h1>
{-aside-}
<ul>
    {% for _, keyword in ipairs(keywords) do %}
    <li>{{keyword}}</li>
    {% end %}
</ul>
{-aside-}
```


##### layout.html

```html
<!DOCTYPE html>
<html>
<head>
<title>{*title*}</title>
</head>
<body>
<article>
    {*view*}
</article>
{% if blocks.aside then %}
<aside>
    {*blocks.aside*}
</aside>
{% end %}
</body>
</html>
```


##### Output

```html
<!DOCTYPE html>
<html>
<head>
<title>Testing lua-resty-template blocks</title>
</head>
<body>
<article>
    <h1>Hello, World!</h1>
</article>
<aside>
    <ul>
        <li>test</li>
        <li>lua</li>
        <li>template</li>
        <li>blocks</li>
    </ul>
</aside>
</body>
</html>
```


### Grandfather-Father-Son Inheritance

Say you have `base.html`, `layout1.html`, `layout2.html` and `page.html`. You want an inheritance like this:
`base.html ➡ layout1.html ➡ page.html` or `base.html ➡ layout2.html ➡ page.html` (actually this nesting is
not limited to three levels).


##### Lua

```lua
local res = require"resty.template".compile("page.html"){} 
```


##### base.html

```html
<html lang='zh'>
   <head>
   <link href="css/bootstrap.min.css" rel="stylesheet">
   {* blocks.page_css *}
   </head>
   <body>
   {* blocks.main *}
   <script src="js/jquery.js"></script>
   <script src="js/bootstrap.min.js"></script>
   {* blocks.page_js *}
   </body>
</html>
```


##### layout1.html

```html
{% layout = "base.html" %}
{-main-}
    <div class="sidebar-1">
      {* blocks.sidebar *}
    </div>
    <div class="content-1">
      {* blocks.content *}
    </div>
{-main-}
```
    

##### layout2.html

```html
{% layout = "base.html" %}
{-main-}
    <div class="sidebar-2">
      {* blocks.sidebar *}
    </div>
    <div class="content-2">
      {* blocks.content *}
    </div>
    <div>I am different from layout1 </div>
{-main-}
```


##### page.html 

```html
{% layout = "layout1.html" %}
{-sidebar-}
  this is sidebar
{-sidebar-}

{-content-}
  this is content
{-content-}

{-page_css-}
  <link href="css/page.css" rel="stylesheet">
{-page_css-}

{-page_js-}
  <script src="js/page.js"></script>
{-page_js-}
```

Or:


##### page.html

```html
{% layout = "layout2.html" %}
{-sidebar-}
  this is sidebar
{-sidebar-}

{-content-}
  this is content
{-content-}

{-page_css-}
  <link href="css/page.css" rel="stylesheet">
{-page_css-}

{-page_js-}
  <script src="js/page.js"></script>
{-page_js-}
```
    

### Macros

[@DDarko](https://github.com/DDarko) mentioned in an [issue #5](https://github.com/bungle/lua-resty-template/issues/5)
that he has a use case where he needs to have macros or parameterized views. That is a nice feature that you can
use with `lua-resty-template`.

To use macros, let's first define some Lua code:

```lua
template.render("macro.html", {
    item = "original",
    items = { a = "original-a", b = "original-b" } 
})
```

And the `macro-example.html`:

```lua
{% local string_macro = [[
<div>{{item}}</div>
]] %}
{* template.compile(string_macro)(context) *}
{* template.compile(string_macro){ item = "string-macro-context" } *}
```

This will output:

```html
<div>original</div>
<div>string-macro-context</div>
```

Now let's add function macro, in `macro-example.html` (you can omit `local` if you want):

```lua
{% local function_macro = function(var, el)
    el = el or "div"
    return "<" .. el .. ">{{" .. var .. "}}</" .. el .. ">\n"
end %}

{* template.compile(function_macro("item"))(context) *}
{* template.compile(function_macro("a", "span"))(items) *}
```

This will output:

```html
<div>original</div>
<span>original-a</span>
```

But this is even more flexible, let's try another function macro:

```lua
{% local function function_macro2(var)
    return template.compile("<div>{{" .. var .. "}}</div>\n")
end %}
{* function_macro2 "item" (context) *}
{* function_macro2 "b" (items) *}
```

This will output:

```html
<div>original</div>
<div>original-b</div>
```

And here is another one:

```lua
{% function function_macro3(var, ctx)
    return template.compile("<div>{{" .. var .. "}}</div>\n")(ctx or context)
end %}
{* function_macro3("item") *}
{* function_macro3("a", items) *}
{* function_macro3("b", items) *}
{* function_macro3("b", { b = "b-from-new-context" }) *}
```

This will output:

```html
<div>original</div>
<div>original-a</div>
<div>original-b</div>
<div>b-from-new-context</div>
```

Macros are really flexible. You may have form-renderers and other helper-macros to have a reusable and
parameterized template output. One thing you should know is that inside code blocks (between `{%` and `%}`)
you cannot have `%}`, but you can work around this using string concatenation `"%" .. "}"`.


### Calling Methods in Templates

You can call string methods (or other table functions) in templates too.


##### Lua

```lua
local template = require "resty.template"
template.render([[
<h1>{{header:upper()}}</h1>
]], { header = "hello, world!" })
```


##### Output

```html
<h1>HELLO, WORLD!</h1>
```


### Embedding Angular or other tags / templating inside the Templates
 
Sometimes you need to mix and match other templates (say client side Javascript templates like Angular) with
server side lua-resty-templates. Say you have this kind of Angular template:

```html
<html ng-app>
 <body ng-controller="MyController">
   <input ng-model="foo" value="bar">
   <button ng-click="changeFoo()">{{buttonText}}</button>
   <script src="angular.js">
 </body>
</html>
```

Now you can see that there is `{{buttonText}}` that is really for Angular templating, and not for lua-resty-template.
You can fix this by wrapping either the whole code with `{-verbatim-}` or `{-raw-}` or only the parts that you want:

```html
{-raw-}
<html ng-app>
 <body ng-controller="MyController">
   <input ng-model="foo" value="bar">
   <button ng-click="changeFoo()">{{buttonText}}</button>
   <script src="angular.js">
 </body>
</html>
{-raw-}
```

or (see the `{(head.html)}` is processed by lua-resty-template):

```html
<html ng-app>
 {(head.html)}
 <body ng-controller="MyController">
   <input ng-model="foo" value="bar">
   <button ng-click="changeFoo()">{-raw-}{{buttonText}}{-raw-}</button>
   <script src="angular.js">
 </body>
</html>
```

You may also use short escaping syntax:

```html
...
<button ng-click="changeFoo()">\{{buttonText}}</button>
...
```


### Embedding Markdown inside the Templates

If you want to embed Markdown (and SmartyPants) syntax inside your templates you can do it by using for example
[`lua-resty-hoedown`](https://github.com/bungle/lua-resty-hoedown) (it depends on LuaJIT). Here is an example of
using that:


##### Lua

```lua
local template = require "resty.template"
template.markdown = require "resty.hoedown"

template.render[=[
<html>
<body>
{*markdown[[
#Hello, World

Testing Markdown.
]]*}
</body>
</html>
]=]
```


##### Output

```html
<html>
<body>
<h1>Hello, World</h1>

<p>Testing Markdown.</p>
</body>
</html>
```

You may also add config parameters that are documented in `lua-resty-hoedown` project.
Say you want also to use SmartyPants:


##### Lua

```lua
local template = require "resty.template"
template.markdown = require "resty.hoedown"

template.render[=[
<html>
<body>
{*markdown([[
#Hello, World

Testing Markdown with "SmartyPants"...
]], { smartypants = true })*}
</body>
</html>
]=]
```


##### Output

```html
<html>
<body>
<h1>Hello, World</h1>

<p>Testing Markdown with &ldquo;SmartyPants&rdquo;&hellip;</p>
</body>
</html>
```

You may also want to add caching layer for your Markdowns, or a helper functions instead of placing
Hoedown library directly  as a template helper function in `template`.   


### Lua Server Pages (LSP) with OpenResty

Lua Server Pages or LSPs is similar to traditional PHP or Microsoft Active Server Pages (ASP)
where you can just place source code files in your document root (of your web server) and have
them processed by compilers of the respective languages (PHP, VBScript, JScript, etc.).
You can emulate quite closely this, sometimes called spaghetti-style of develoment, easily with
`lua-resty-template`. Those that have been doing ASP.NET Web Forms development, know a concept
of Code Behind files. There is something similar, but this time we call it Layout in Front here
(you may include Lua modules with normal `require` calls if you wish in LSPs). To help you
understand the concepts, let's have a small example:


##### nginx.conf:

```nginx
http {
  init_by_lua '
    require "resty.core"
    template = require "resty.template"
    template.caching(false); -- you may remove this on production
  ';
  server {
    location ~ \.lsp$ {
      default_type text/html;
      content_by_lua 'template.render(ngx.var.uri)';
    }
  }
}
```

The above configuration creates a global `template` variable in Lua environment (you may not want that).
We also created location to match all `.lsp` files (or locations), and then we just render the template.

Let's imagine that the request is for `index.lsp`.


##### index.lsp

```html
{%
layout = "layouts/default.lsp"
local title = "Hello, World!"
%}
<h1>{{title}}</h1>
```

Here you can see that this file includes a little bit of a view (`<h1>{{title}}</h1>`) in addition to some
Lua code that we want to run. If you want to have a pure code file with Layout in Front, then just don't
write any view code in this file. The `layout` variable is already defined in views as documented else
where in this documentation. Now let's see the other files too.


##### layouts/default.lsp

```html
<html>
{(include/header.lsp)}
<body>
{*view*}
</body>
</html>
```

Here we have a layout to decorate the `index.lsp`, but we also have include here, so let's look at it.


##### include/header.lsp

```html
<head>
  <title>Testing Lua Server Pages</title>
</head>
```

Static stuff here only.


##### Output

The final output will look like this:

```html
<html>
<head>
  <title>Testing Lua Server Pages</title>
</head>
<body>
  <h1>Hello, World!</h1>
</body>
</html>
```

As you can see, `lua-resty-template` can be quite flexibile and easy to start with. Just place
files under your document root and use the normal save-and-refresh style of development. The
server will automatically pick the new files and reload the templates (if the caching is turned
of) on save.

If you want to pass variables to layouts or includes you can add stuff to context table (in the
example below see `context.title`):

```html
{%
layout = "layouts/default.lsp"
local title = "Hello, World!"
context.title = 'My Application - ' .. title
%}
<h1>{{title}}</h1>
```


## FAQ

### How Do I Clear the Template Cache

`lua-resty-template` automatically caches (if caching is enabled) the resulting template functions
in `template.cache` table. You can clear the cache by issuing `template.cache = {}`.


### Where is `lua-resty-template` Used

* [jd.com](http://www.jd.com/) – Jingdong Mall (Chinese: 京东商城; pinyin: Jīngdōng Shāngchéng),
formerly 360Buy, is a Chinese electronic commerce company

Please let me know if there are errors or old information in this list. 


## Alternatives

You may also look at these (as alternatives, or to mix them with `lua-resty-template`):

* lemplate (https://github.com/openresty/lemplate)
* lua-resty-tags (https://github.com/bungle/lua-resty-tags)
* lua-resty-hoedown (https://github.com/bungle/lua-resty-hoedown)
* etlua (https://github.com/leafo/etlua)
* lua-template (https://github.com/dannote/lua-template)
* lua-resty-tmpl (https://github.com/lloydzhou/lua-resty-tmpl) (a fork of the [lua-template](https://github.com/dannote/lua-template))
* htmlua (https://github.com/benglard/htmlua)
* cgilua (http://keplerproject.github.io/cgilua/manual.html#templates)
* orbit (http://keplerproject.github.io/orbit/pages.html)
* turbolua mustache (http://turbolua.org/doc/web.html#mustache-templating)
* pl.template (http://stevedonovan.github.io/Penlight/api/modules/pl.template.html)
* lustache (https://github.com/Olivine-Labs/lustache)
* luvstache (https://github.com/james2doyle/luvstache)
* luaghetti (https://github.com/AterCattus/luaghetti)
* lub.Template (http://doc.lubyk.org/lub.Template.html)
* lust (https://github.com/weshoke/Lust)
* templet (http://colberg.org/lua-templet/)
* luahtml (https://github.com/TheLinx/LuaHTML)
* mixlua (https://github.com/LuaDist/mixlua)
* lutem (https://github.com/daly88/lutem)
* tirtemplate (https://github.com/torhve/LuaWeb/blob/master/tirtemplate.lua)
* cosmo (http://cosmo.luaforge.net/)
* lua-codegen (http://fperrad.github.io/lua-CodeGen/)
* groucho (https://github.com/hanjos/groucho)
* simple lua preprocessor (http://lua-users.org/wiki/SimpleLuaPreprocessor)
* slightly less simple lua preprocessor (http://lua-users.org/wiki/SlightlyLessSimpleLuaPreprocessor)
* ltp (http://www.savarese.com/software/ltp/)
* slt (https://code.google.com/p/slt/)
* slt2 (https://github.com/henix/slt2)
* luasp (http://luasp.org/)
* view0 (https://bitbucket.org/jimstudt/view0)
* leslie (https://code.google.com/p/leslie/)
* fraudster (https://bitbucket.org/sphen_lee/fraudster)
* lua-haml (https://github.com/norman/lua-haml)
* lua-template (https://github.com/tgn14/Lua-template)
* hige (https://github.com/nrk/hige)
* mod_pLua (https://sourceforge.net/p/modplua/wiki/Home/)
* lapis html generation (http://leafo.net/lapis/reference.html#html-generation)

`lua-resty-template` *was originally forked from Tor Hveem's* `tirtemplate.lua` *that he had extracted
from Zed Shaw's Tir web framework (http://tir.mongrel2.org/). Thank you Tor, and Zed for your earlier
contributions.*


## Benchmarks

There is a small microbenchmark located here:
https://github.com/bungle/lua-resty-template/blob/master/lib/resty/template/microbenchmark.lua

There is also a regression in LuaJIT that affects the results. If you want your LuaJIT patched against this,
you need to merge this pull request: https://github.com/LuaJIT/LuaJIT/pull/174.

Others have [reported](https://github.com/bungle/lua-resty-template/issues/21#issuecomment-226786051)
that in simple benchmarks running this template engine actually beats Nginx serving static files by
a factor of three. So I guess this engine is quite fast. 


##### Lua

```lua
local benchmark = require "resty.template.microbenchmark"
benchmark.run()
-- You may also pass iteration count (by default it is 1,000)
benchmark.run(100)
```

Here are some results from my desktop (old 2010 Mac Pro):
```
<lua|luajit|resty> -e 'require "resty.template.microbenchmark".run()'
```
`


##### Lua 5.1.5  Copyright (C) 1994-2012 Lua.org, PUC-Rio

```
Running 1000 iterations in each test
    Parsing Time: 0.010759
Compilation Time: 0.054640 (template)
Compilation Time: 0.000213 (template, cached)
  Execution Time: 0.061851 (same template)
  Execution Time: 0.006722 (same template, cached)
  Execution Time: 0.092698 (different template)
  Execution Time: 0.009537 (different template, cached)
  Execution Time: 0.092452 (different template, different context)
  Execution Time: 0.010106 (different template, different context, cached)
      Total Time: 0.338978
```


##### Lua 5.2.4  Copyright (C) 1994-2015 Lua.org, PUC-Rio

```
Running 1000 iterations in each test
    Parsing Time: 0.011633
Compilation Time: 0.060598 (template)
Compilation Time: 0.000243 (template, cached)
  Execution Time: 0.068009 (same template)
  Execution Time: 0.007307 (same template, cached)
  Execution Time: 0.071339 (different template)
  Execution Time: 0.007150 (different template, cached)
  Execution Time: 0.066766 (different template, different context)
  Execution Time: 0.006940 (different template, different context, cached)
      Total Time: 0.299985
```


##### Lua 5.3.5  Copyright (C) 1994-2018 Lua.org, PUC-Rio

```
Running 1000 iterations in each test
    Parsing Time: 0.012458
Compilation Time: 0.050013 (template)
Compilation Time: 0.000249 (template, cached)
  Execution Time: 0.057579 (same template)
  Execution Time: 0.006959 (same template, cached)
  Execution Time: 0.065352 (different template)
  Execution Time: 0.007133 (different template, cached)
  Execution Time: 0.060965 (different template, different context)
  Execution Time: 0.007726 (different template, different context, cached)
      Total Time: 0.268434
```


##### Lua 5.4.0  Copyright (C) 1994-2019 Lua.org, PUC-Rio

```
Running 1000 iterations in each test
    Parsing Time: 0.009466
Compilation Time: 0.053116 (template)
Compilation Time: 0.000209 (template, cached)
  Execution Time: 0.059017 (same template)
  Execution Time: 0.006129 (same template, cached)
  Execution Time: 0.061882 (different template)
  Execution Time: 0.006613 (different template, cached)
  Execution Time: 0.059104 (different template, different context)
  Execution Time: 0.005761 (different template, different context, cached)
      Total Time: 0.261297
```


##### LuaJIT 2.0.5 -- Copyright (C) 2005-2017 Mike Pall. http://luajit.org/

```
Running 1000 iterations in each test
    Parsing Time: 0.005198
Compilation Time: 0.029687 (template)
Compilation Time: 0.000082 (template, cached)
  Execution Time: 0.033824 (same template)
  Execution Time: 0.003130 (same template, cached)
  Execution Time: 0.075899 (different template)
  Execution Time: 0.007027 (different template, cached)
  Execution Time: 0.070269 (different template, different context)
  Execution Time: 0.007456 (different template, different context, cached)
      Total Time: 0.232572
```


##### LuaJIT 2.1.0-beta3 -- Copyright (C) 2005-2017 Mike Pall. http://luajit.org/

```
Running 1000 iterations in each test
    Parsing Time: 0.003647
Compilation Time: 0.027145 (template)
Compilation Time: 0.000083 (template, cached)
  Execution Time: 0.034685 (same template)
  Execution Time: 0.002801 (same template, cached)
  Execution Time: 0.073466 (different template)
  Execution Time: 0.010836 (different template, cached)
  Execution Time: 0.068790 (different template, different context)
  Execution Time: 0.009818 (different template, different context, cached)
      Total Time: 0.231271
```


##### resty (resty 0.23, nginx version: openresty/1.15.8.2)

```
Running 1000 iterations in each test
    Parsing Time: 0.003980
Compilation Time: 0.025983 (template)
Compilation Time: 0.000066 (template, cached)
  Execution Time: 0.032752 (same template)
  Execution Time: 0.002740 (same template, cached)
  Execution Time: 0.036111 (different template)
  Execution Time: 0.005559 (different template, cached)
  Execution Time: 0.032453 (different template, different context)
  Execution Time: 0.006057 (different template, different context, cached)
      Total Time: 0.145701
```

I have not yet compared the results against the alternatives.


## Changes

The changes of every release of this module is recorded in
[Changes.md](https://github.com/bungle/lua-resty-template/blob/master/Changes.md) file.


## See Also

* [lua-resty-route](https://github.com/bungle/lua-resty-route) — Routing library
* [lua-resty-reqargs](https://github.com/bungle/lua-resty-reqargs) — Request arguments parser
* [lua-resty-session](https://github.com/bungle/lua-resty-session) — Session library
* [lua-resty-validation](https://github.com/bungle/lua-resty-validation) — Validation and filtering library


## Roadmap

Some things I and the community wishes to be added:

- Better debugging capabilities and better error messages
- Proper sandboxing


## License

`lua-resty-template` uses three clause BSD license (because it was originally forked from one that uses it).

```
Copyright (c) 2014 - 2020, Aapo Talvensaari
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
  list of conditions and the following disclaimer in the documentation and/or
  other materials provided with the distribution.

* Neither the name of the {organization} nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
