local ngx_re_gmatch = ngx.re.gmatch
local ngx_re_sub = ngx.re.sub
local ngx_re_find = ngx.re.find
local ngx_log = ngx.log
local ngx_WARN = ngx.WARN

--[[
A connection function that incorporates:
  - tcp connect
  - ssl handshake
  - http proxy
Due to this it will be better at setting up a socket pool where connections can
be kept alive.


Call it with a single options table as follows:

client:connect {
    scheme = "https"        -- scheme to use, or nil for unix domain socket
    host = "myhost.com",    -- target machine, or a unix domain socket
    port = nil,             -- port on target machine, will default to 80/443 based on scheme
    pool = nil,             -- connection pool name, leave blank! this function knows best!
    pool_size = nil,        -- options as per: https://github.com/openresty/lua-nginx-module#tcpsockconnect
    backlog = nil,

    -- ssl options as per: https://github.com/openresty/lua-nginx-module#tcpsocksslhandshake
    ssl_reused_session = nil
    ssl_server_name = nil,
    ssl_send_status_req = nil,
    ssl_verify = true,      -- NOTE: defaults to true
    ctx = nil,              -- NOTE: not supported

    -- mTLS options: These require support for mTLS in cosockets, which first
    -- appeared in `ngx_http_lua_module` v0.10.23.
    ssl_client_cert = nil,
    ssl_client_priv_key = nil,

    proxy_opts,             -- proxy opts, defaults to global proxy options
}
]]
local function connect(self, options)
    local sock = self.sock
    if not sock then
        return nil, "not initialized"
    end

    local ok, err

    local request_scheme = options.scheme
    local request_host = options.host
    local request_port = options.port

    local poolname = options.pool
    local pool_size = options.pool_size
    local backlog = options.backlog

    if request_scheme and not request_port then
        request_port = (request_scheme == "https" and 443 or 80)
    elseif request_port and not request_scheme then
        return nil, "'scheme' is required when providing a port"
    end

    -- ssl settings
    local ssl, ssl_reused_session, ssl_server_name
    local ssl_verify, ssl_send_status_req, ssl_client_cert, ssl_client_priv_key
    if request_scheme == "https" then
        ssl = true
        ssl_reused_session = options.ssl_reused_session
        ssl_server_name = options.ssl_server_name
        ssl_send_status_req = options.ssl_send_status_req
        ssl_verify = true -- default
        if options.ssl_verify == false then
            ssl_verify = false
        end
        ssl_client_cert = options.ssl_client_cert
        ssl_client_priv_key = options.ssl_client_priv_key
    end

    -- proxy related settings
    local proxy, proxy_uri, proxy_authorization, proxy_host, proxy_port, path_prefix
    proxy = options.proxy_opts or self.proxy_opts

    if proxy then
        if request_scheme == "https" then
            proxy_uri = proxy.https_proxy
            proxy_authorization = proxy.https_proxy_authorization
        else
            proxy_uri = proxy.http_proxy
            proxy_authorization = proxy.http_proxy_authorization
            -- When a proxy is used, the target URI must be in absolute-form
            -- (RFC 7230, Section 5.3.2.). That is, it must be an absolute URI
            -- to the remote resource with the scheme, host and an optional port
            -- in place.
            --
            -- Since _format_request() constructs the request line by concatenating
            -- params.path and params.query together, we need to modify the path
            -- to also include the scheme, host and port so that the final form
            -- in conformant to RFC 7230.
            path_prefix = "http://" .. request_host .. (request_port == 80 and "" or (":" .. request_port))
        end
        if not proxy_uri then
            proxy = nil
            proxy_authorization = nil
            path_prefix = nil
        end
    end

    if proxy and proxy.no_proxy then
        -- Check if the no_proxy option matches this host. Implementation adapted
        -- from lua-http library (https://github.com/daurnimator/lua-http)
        if proxy.no_proxy == "*" then
            -- all hosts are excluded
            proxy = nil

        else
            local host = request_host
            local no_proxy_set = {}
            -- wget allows domains in no_proxy list to be prefixed by "."
            -- e.g. no_proxy=.mit.edu
            for host_suffix in ngx_re_gmatch(proxy.no_proxy, "\\.?([^,]+)") do
                no_proxy_set[host_suffix[1]] = true
            end

            -- From curl docs:
            -- matched as either a domain which contains the hostname, or the
            -- hostname itself. For example local.com would match local.com,
            -- local.com:80, and www.local.com, but not www.notlocal.com.
            --
            -- Therefore, we keep stripping subdomains from the host, compare
            -- them to the ones in the no_proxy list and continue until we find
            -- a match or until there's only the TLD left
            repeat
                if no_proxy_set[host] then
                    proxy = nil
                    proxy_uri = nil
                    proxy_authorization = nil
                    break
                end

                -- Strip the next level from the domain and check if that one
                -- is on the list
                host = ngx_re_sub(host, "^[^.]+\\.", "")
            until not ngx_re_find(host, "\\.")
        end
    end

    if proxy then
        local proxy_uri_t
        proxy_uri_t, err = self:parse_uri(proxy_uri)
        if not proxy_uri_t then
            return nil, "uri parse error: ", err
        end

        local proxy_scheme = proxy_uri_t[1]
        if proxy_scheme ~= "http" then
            return nil, "protocol " .. tostring(proxy_scheme) ..
                        " not supported for proxy connections"
        end
        proxy_host = proxy_uri_t[2]
        proxy_port = proxy_uri_t[3]
    end

    -- construct a poolname unique within proxy and ssl info
    if not poolname then
        poolname = (request_scheme or "")
                   .. ":" .. request_host
                   .. ":" .. tostring(request_port)
                   .. ":" .. tostring(ssl)
                   .. ":" .. (ssl_server_name or "")
                   .. ":" .. tostring(ssl_verify)
                   .. ":" .. (proxy_uri or "")
                   .. ":" .. (request_scheme == "https" and proxy_authorization or "")
        -- in the above we only add the 'proxy_authorization' as part of the poolname
        -- when the request is https. Because in that case the CONNECT request (which
        -- carries the authorization header) is part of the connect procedure, whereas
        -- with a plain http request the authorization is part of the actual request.
    end

    -- do TCP level connection
    local tcp_opts = { pool = poolname, pool_size = pool_size, backlog = backlog }
    if proxy then
        -- proxy based connection
        ok, err = sock:connect(proxy_host, proxy_port, tcp_opts)
        if not ok then
            return nil, "failed to connect to: " .. (proxy_host or "") ..
                        ":" .. (proxy_port or "") ..
                        ": ", err
        end

        if ssl and sock:getreusedtimes() == 0 then
            -- Make a CONNECT request to create a tunnel to the destination through
            -- the proxy. The request-target and the Host header must be in the
            -- authority-form of RFC 7230 Section 5.3.3. See also RFC 7231 Section
            -- 4.3.6 for more details about the CONNECT request
            local destination = request_host .. ":" .. request_port
            local res
            res, err = self:request({
                method = "CONNECT",
                path = destination,
                headers = {
                    ["Host"] = destination,
                    ["Proxy-Authorization"] = proxy_authorization,
                }
            })

            if not res then
                return nil, "failed to issue CONNECT to proxy:", err
            end

            if res.status < 200 or res.status > 299 then
                return nil, "failed to establish a tunnel through a proxy: " .. res.status
            end
        end

    elseif not request_port then
        -- non-proxy, without port -> unix domain socket
        ok, err = sock:connect(request_host, tcp_opts)
        if not ok then
            return nil, err
        end

    else
        -- non-proxy, regular network tcp
        ok, err = sock:connect(request_host, request_port, tcp_opts)
        if not ok then
            return nil, err
        end
    end

    local ssl_session
    -- Now do the ssl handshake
    if ssl and sock:getreusedtimes() == 0 then

        -- Experimental mTLS support
        if ssl_client_cert and ssl_client_priv_key then
          if type(sock.setclientcert) ~= "function" then
            ngx_log(ngx_WARN, "cannot use SSL client cert and key without mTLS support")

          else
            ok, err = sock:setclientcert(ssl_client_cert, ssl_client_priv_key)
            if not ok then
              ngx_log(ngx_WARN, "could not set client certificate: ", err)
            end
          end
        end

        ssl_session, err = sock:sslhandshake(ssl_reused_session, ssl_server_name, ssl_verify, ssl_send_status_req)
        if not ssl_session then
            self:close()
            return nil, err
        end
    end

    self.host = request_host
    self.port = request_port
    self.keepalive = true
    self.ssl = ssl
    -- set only for http, https has already been handled
    self.http_proxy_auth = request_scheme ~= "https" and proxy_authorization or nil
    self.path_prefix = path_prefix

    return true, nil, ssl_session
end

return connect
