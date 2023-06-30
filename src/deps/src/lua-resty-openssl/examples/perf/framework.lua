local ffi = require "ffi"
local C = ffi.C
local ITER = 2000

local get_duration
do
    ffi.cdef [[

    typedef long time_t;
    typedef int clockid_t;
    typedef struct timespec {
            time_t   tv_sec;        /* seconds */
            long     tv_nsec;       /* nanoseconds */
    } nanotime;

    int clock_gettime(clockid_t clk_id, struct timespec *tp);

    ]]
    local time_ns
    do
      local nanop = ffi.new("nanotime[1]")
      function time_ns()
        -- CLOCK_REALTIME -> 0
        C.clock_gettime(0, nanop)
        local t = nanop[0]

        return tonumber(t.tv_sec) * 1e9 + tonumber(t.tv_nsec)
      end
    end

    local last = 0 
    get_duration = function()
        local n = time_ns()
        local d = n - last
        last = n
        return d
    end
end

local function hmt(t)
    if t > 1e9 * 0.01 then
        return string.format("%.3f s", t/1e9)
    elseif t > 1e6 * 0.01 then
        return string.format("%.3f ms", t/1e6)
    else
        return string.format("%d ns", t)
    end
end

-- return sum, avg, max
local function stat(t)
    if not t then
        return 0, 0, 0
    end

    local v = 0
    local max = 0
    for _, i in ipairs(t) do
        v = v + i
        if i > max then
            max = i
        end
    end
    return v, v/#t, max 
end

local function test(desc, r, iter)
    print("RUNNING " .. ITER .. " ITERATIONS FOR " .. desc)
    local data = table.new(ITER, 0)
    for i=1, ITER do
        get_duration()
        local ok, err = r()
        data[i] = get_duration()
        assert(ok, err)
    end

    local sum, avg, max = stat(data)

    print(string.format("FINISHED in\t%s (%d op/s)\nAVG\t%s\tMAX\t%s", hmt(sum), 1e9/avg, hmt(avg), hmt(max))) 
    print(string.rep("-", 64))
end

local function set_iteration(i)
    ITER = i
end

print("LOADING TEST FROM " .. arg[0])
print(string.rep("=", 64))

return {
    test = test,
    set_iteration = set_iteration,
}
