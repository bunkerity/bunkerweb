# vi:ft=

use lib '.';
use t::TestKiller;

plan tests => 3 * blocks();

no_long_string();
#no_diff();

run_tests();

__DATA__

=== TEST 1: failure to load librestysignal.so
--- config
    location = /t {
        content_by_lua_block {
            local cpath = package.cpath
            package.cpath = "/foo/?.so;/bar/?.so;"

            local ok, perr = pcall(require, "resty.signal")
            if not ok then
                ngx.say(perr)
            end

            package.cpath = cpath
        }
    }
--- response_body
could not load librestysignal.so from the following paths:
/foo/librestysignal.so
/bar/librestysignal.so
--- no_error_log
[error]
