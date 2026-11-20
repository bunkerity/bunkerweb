local script_dir = arg[0]:match("^(.*)/[^/]+$") or "."
package.path = script_dir .. "/../../src/bw/lua/?.lua;" .. package.path

local cluster_nodes = ""
package.loaded["bunkerweb.utils"] = {
	get_variable = function(name)
		assert(name == "REDIS_CLUSTER_NODES")
		return cluster_nodes
	end,
}
local rk = require "bunkerweb.rediskeys"

local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	if ok then
		print("PASS " .. name)
	else
		failures = failures + 1
		print("FAIL " .. name .. ": " .. tostring(err))
	end
end
local function eq(a, b)
	assert(a == b, ("expected %q got %q"):format(tostring(b), tostring(a)))
end

it("cluster_mode follows REDIS_CLUSTER_NODES", function()
	cluster_nodes = ""
	eq(rk.cluster_mode(), false)
	cluster_nodes = "redis-a:6379"
	eq(rk.cluster_mode(), true)
end)
it("cluster_mode treats whitespace-only nodes as unset", function()
	cluster_nodes = "  "
	eq(rk.cluster_mode(), false)
	cluster_nodes = "\t\n"
	eq(rk.cluster_mode(), false)
end)
it("legacy ban names unchanged", function()
	eq(rk.ban("bans_ip_1.2.3.4", false), "bans_ip_1.2.3.4")
	eq(rk.ban("bans_service_app.example_ip_1.2.3.4", false), "bans_service_app.example_ip_1.2.3.4")
end)
it("cluster ban names tag the IP", function()
	eq(rk.ban("bans_ip_1.2.3.4", true), "bans_ip_{1.2.3.4}")
	eq(rk.ban("bans_service_app.example_ip_1.2.3.4", true), "bans_service_app.example_ip_{1.2.3.4}")
end)
it("IPv6 compressed and mapped", function()
	eq(rk.ban("bans_ip_2001:db8::1", true), "bans_ip_{2001:db8::1}")
	eq(rk.ban("bans_service_s_ip_::ffff:1.2.3.4", true), "bans_service_s_ip_{::ffff:1.2.3.4}")
end)
it("service containing _ip_ and braces", function()
	eq(rk.ban("bans_service_my_ip_app_ip_1.2.3.4", true), "bans_service_my_ip_app_ip_{1.2.3.4}")
	eq(rk.ban("bans_service_{a}.example_ip_1.2.3.4", true), "bans_service_%7Ba%7D.example_ip_{1.2.3.4}")
end)
it("badbehavior names", function()
	eq(rk.badbehavior("1.2.3.4", nil, false), "plugin_bad_behavior_1.2.3.4")
	eq(rk.badbehavior("1.2.3.4", "app", false), "plugin_bad_behavior_app_1.2.3.4")
	eq(rk.badbehavior("1.2.3.4", nil, true), "plugin_bad_behavior_{1.2.3.4}")
	eq(rk.badbehavior("1.2.3.4", "{x}", true), "plugin_bad_behavior_%7Bx%7D_{1.2.3.4}")
end)
it("escape", function()
	eq(rk.escape("plugin_limit_app1.2.3.4/{x}"), "plugin_limit_app1.2.3.4/%7Bx%7D")
	eq(rk.escape("no-braces"), "no-braces")
	eq(rk.escape("a%7Bb"), "a%257Bb")
	eq(rk.escape("a{b"), "a%7Bb")
	eq(rk.escape("a%b"), "a%25b")
	eq(rk.escape("%25"), "%2525")
end)
it("reports keys", function()
	local f = { "ip", "country" }
	local legacy = rk.reports(false, f)
	eq(#legacy, 6)
	eq(legacy[1], "requests")
	eq(legacy[2], "requests:facets:initialized")
	eq(legacy[3], "requests:facets:rebuilding")
	eq(legacy[4], "requests:facets:oomprobe")
	eq(legacy[5], "requests:facet:ip")
	eq(legacy[6], "requests:facet:country")
	local cl = rk.reports(true, f)
	eq(cl[1], "{requests}")
	eq(cl[2], "{requests}:facets:initialized")
	eq(cl[6], "{requests}:facet:country")
end)
it("cluster_config_error", function()
	eq(rk.cluster_config_error("", "s:26379", "3"), nil)
	eq(rk.cluster_config_error("a:7000", "", "0"), nil)
	eq(rk.cluster_config_error("a:7000", "", ""), nil)
	assert(rk.cluster_config_error("a:7000", "s:26379", "0"):find("REDIS_SENTINEL_HOSTS", 1, true))
	eq(rk.cluster_config_error("a:7000", "", "00"), nil)
	assert(rk.cluster_config_error("a:7000", "", "2"):find("REDIS_DATABASE", 1, true))
	assert(rk.cluster_config_error("a:7000", "", "x"):find("REDIS_DATABASE", 1, true))
	eq(rk.cluster_config_error("  ", "s:26379", "3"), nil)
end)
it("parse_nodes", function()
	local n = rk.parse_nodes("  redis-a:7000 redis-b  [::1]:7001  10.0.0.1:7002 ")
	eq(#n, 4)
	eq(n[1].ip, "redis-a")
	eq(n[1].port, 7000)
	eq(n[2].ip, "redis-b")
	eq(n[2].port, 6379)
	eq(n[3].ip, "[::1]")
	eq(n[3].port, 7001)
	eq(n[4].ip, "10.0.0.1")
	eq(n[4].port, 7002)
end)

it("cs_epoch keys", function()
	assert(rk.cs_epoch("1.2.3.4", false) == "cs_epoch_1.2.3.4")
	assert(rk.cs_epoch("1.2.3.4", true) == "cs_epoch_{1.2.3.4}")
	assert(rk.cs_epoch("2001:db8::1", true) == "cs_epoch_{2001:db8::1}")
	assert(
		rk.ban("bans_cs_service_a_ip_b.example.com_ip_1.2.3.4", true)
			== "bans_cs_service_a_ip_b.example.com_ip_{1.2.3.4}"
	)
end)

os.exit(failures == 0 and 0 or 1)
