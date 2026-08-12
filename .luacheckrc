-- "delay" was declared here to silence a bare global in limit.lua that nothing ever
-- assigned, so the rate-limit shm mirror was written with no TTL. Keep it out : W113
-- on any future bare `delay` is what stops that regression from coming back.
globals = { "ngx", "unpack" }
ignore = {"411"}
