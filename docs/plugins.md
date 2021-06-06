# Plugins

Bunkerized-nginx comes with a plugin system that lets you extend the core with extra security features. To add a plugin you will need to download it, edit its settings and mount it to the `/plugins` volume.

## Official plugins

- [ClamAV](https://github.com/bunkerity/bunkerized-nginx-clamav) : automatically scan uploaded files and deny access if a virus is detected

## Community plugins

If you have made a plugin and want it to be listed here, feel free to [create a pull request](https://github.com/bunkerity/bunkerized-nginx/pulls) and edit that section.

## Use a plugin

The generic way of using a plugin consists of :
- Download it to a folder (e.g. : myplugin/)
- Edit the settings inside the plugin.json files (e.g. : myplugin/plugin.json)
- Mount the plugin folder to the /plugins/plugin-id inside the container (e.g. : /where/is/myplugin:/plugins/myplugin)

To check if the plugin is loaded you should see log entries like that :

```log
2021/06/05 09:19:47 [error] 104#104: [PLUGINS] *NOT AN ERROR* plugin MyPlugin/1.0 has been loaded
```

## Write a plugin

A plugin is composed of a plugin.json which contains metadata (e.g. : name, settings, ...) and a set of LUA files for the plugin code.

### plugin.json

```json
{
	"id": "myplugin",
	"name": "My Plugin",
	"description": "Short description of my plugin.",
	"version": "1.0",
	"settings": {
		"MY_SETTING": "value1",
		"ANOTHER_SETTING": "value2",
	}
}
```

The `id` value is really important because it must match the subfolder name inside the `plugins` volume. Choose one which isn't already used to avoid conflicts.

Settings names and default values can be choosen freely. There will be no conflict when you retrieve them because they will be prefixed with your plugin id (e.g. : `myplugin_MY_SETTING`).

### Main code

```lua
local M		= {}
local logger	= require "logger"

-- this function will be called for each request
-- the name MUST be check without any argument
function M.check ()

	-- the logger.log function lets you write into the logs
	logger.log(ngx.NOTICE, "MyPlugin", "check called")

	-- here is how to retrieve a setting
	local my_setting = ngx.shared.plugins_data:get("pluginid_MY_SETTING")

	-- a dummy example to show how to block a request
	if my_setting == "block" then
		ngx.exit(ngx.HTTP_FORBIDDEN)
	end

end

return M
```

That file must have the same name as the `id` defined in the plugin.json with a .lua suffix (e.g. : `myplugin.lua`).

Under the hood, bunkerized-nginx uses the [lua nginx module](https://github.com/openresty/lua-nginx-module) therefore you should be able to access to the whole **ngx.\*** functions.

### Dependencies

Since the core already uses some external libraries you can use it in your own plugins too (see the [compile.sh](https://github.com/bunkerity/bunkerized-nginx/blob/master/compile.sh) file and the [core lua files](https://github.com/bunkerity/bunkerized-nginx/tree/master/lua)).

In case you need to add dependencies, you can do it by placing the corresponding files into the same folder of your main plugin code. Here is an example with a file named **dependency.lua** :

```lua
local M = {}

function M.my_function ()
	return "42"
end

return M
```

To include it from you main code you will need to prefix it with your plugin id like that :

```lua
...
local my_dependency = require "pluginid.dependency"

function M.check ()
	...
	local my_value = my_dependency.my_function()
	...
end
...
```

