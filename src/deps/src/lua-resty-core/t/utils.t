# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

plan tests => repeat_each() * blocks() * 3;

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->error_log) {
        $block->set_value("no_error_log", "[error]");
    }

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }
});

no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: utils.str_replace_char() sanity (replaces a single character)
--- config
    location /t {
        content_by_lua_block {
            local utils = require "resty.core.utils"

            local strings = {
                "Header_Name",
                "_Header_Name_",
                "Header__Name",
                "Header-Name",
                "Hello world",
            }

            for i = 1, #strings do
                ngx.say(utils.str_replace_char(strings[i], "_", "-"))
            end
        }
    }
--- response_body
Header-Name
-Header-Name-
Header--Name
Header-Name
Hello world



=== TEST 2: utils.str_replace_char() JIT compiles when match
--- config
    location /t {
        content_by_lua_block {
            local utils = require "resty.core.utils"

            for i = 1, $TEST_NGINX_HOTLOOP * 10 do
                utils.str_replace_char("Header_Name", "_", "-")
            end
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/,
--- no_error_log
[error]



=== TEST 3: utils.str_replace_char() JIT compiles when no match
--- config
    location /t {
        content_by_lua_block {
            local utils = require "resty.core.utils"

            for i = 1, $TEST_NGINX_HOTLOOP * 10 do
                utils.str_replace_char("Header_Name", "-", "_")
            end
        }
    }
--- ignore_response_body
--- error_log eval
qr/\[TRACE\s+\d+ content_by_lua\(nginx\.conf:\d+\):4 loop\]/,
--- no_error_log
[error]



=== TEST 4: utils.str_replace_char() replacing more than one character is not supported
--- config
    location /t {
        content_by_lua_block {
            local utils = require "resty.core.utils"

            local strings = {
                "Header01Name",
                "01Header01Name01",
                "Header0Name",
                "Header1Name",
                "Hello world",
            }

            for i = 1, #strings do
                ngx.say(utils.str_replace_char(strings[i], "02", "02"))
            end
        }
    }
--- response_body
Header01Name
01Header01Name01
Header0Name
Header1Name
Hello world
