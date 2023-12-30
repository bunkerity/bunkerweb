local ipairs, type = ipairs, type

local ngx_null = ngx.null

local tbl_insert = table.insert
local ok, tbl_new = pcall(require, "table.new")
if not ok then
    tbl_new = function (narr, nrec) return {} end -- luacheck: ignore 212
end


local _M = {
    _VERSION = '0.11.0'
}


function _M.get_master(sentinel, master_name)
    local res, err = sentinel:sentinel(
        "get-master-addr-by-name",
        master_name
    )
    if res and res ~= ngx_null and res[1] and res[2] then
        return { host = res[1], port = res[2] }
    elseif res == ngx_null then
        return nil, "invalid master name"
    else
        return nil, err
    end
end


function _M.get_slaves(sentinel, master_name)
    local res, err = sentinel:sentinel("slaves", master_name)

    if res and type(res) == "table" then
        local hosts = tbl_new(#res, 0)
        for _,slave in ipairs(res) do
            local num_recs = #slave
            local host = tbl_new(0, num_recs + 1)
            for i = 1, num_recs, 2 do
                host[slave[i]] = slave[i + 1]
            end

            local master_link_status_ok = host["master-link-status"] == "ok"
            local is_down = host["flags"] and (string.find(host["flags"],"s_down")
                or string.find(host["flags"],"disconnected"))
            if master_link_status_ok and not is_down then
                host.host = host.ip -- for parity with other functions
                tbl_insert(hosts, host)
            end
        end
        if hosts[1] ~= nil then
            return hosts
        else
            return nil, "no slaves available"
        end
    else
        return nil, err
    end
end


return _M
