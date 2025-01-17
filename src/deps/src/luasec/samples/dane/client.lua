
local socket = require "socket";
local ssl = require "ssl";

local dns = require "lunbound".new();


local cfg = {
	protocol = "tlsv1_2",
	mode = "client",
	ciphers = "DEFAULT",
	capath = "/etc/ssl/certs",
	verify = "peer",
	dane = true,
};

local function daneconnect(host, port)
   port = port or "443";
	local conn = ssl.wrap(socket.connect(host, port), cfg);

	local tlsa = dns:resolve("_" .. port .. "._tcp." .. host, 52);
	assert(tlsa.secure, "Insecure DNS");

	assert(conn:setdane(host));
	for i = 1, tlsa.n do
		local usage, selector, mtype = tlsa[i] :byte(1, 3);
		assert(conn:settlsa(usage, selector, mtype, tlsa[i] :sub(4, - 1)));
	end

	assert(conn:dohandshake());
	return conn;
end

if not ... then
   print("Usage: client.lua example.com [port]");
   return os.exit(1);
end
local conn = daneconnect(...);

print(conn:getpeerverification());
