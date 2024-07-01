# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4 - 4);

add_block_preprocessor(sub {
    my $block = shift;

    my $http_config = $block->http_config || '';
    my $init_by_lua_block = $block->init_by_lua_block || '';

    $http_config .= <<_EOC_;
    lua_package_path '$t::TestCore::lua_package_path';
    init_by_lua_block {
        $t::TestCore::init_by_lua_block
        $init_by_lua_block
    }
_EOC_

    $block->set_value("http_config", $http_config);
});

no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: PCRE MAP_JIT workaround on macOS
--- init_by_lua_block
    ngx.re.match("c", "test", "jo")
--- config
    location /re {
        content_by_lua_block {
            ngx.say(ngx.re.sub("c", "a", "b", ""))
            ngx.say(ngx.re.sub("c", "a", "b", "jo"))
        }
    }
--- request
GET /re
--- response_body
c0
c0
--- grep_error_log eval
qr/.+parse_regex_opts\(\): .*? disabled in init phase under macOS/
--- grep_error_log_out eval
qr/parse_regex_opts\(\): regex compilation disabled in init phase under macOS
.*?parse_regex_opts\(\): regex compilation cache disabled in init phase under macOS/s
--- no_error_log
[error]
--- skip_eval
4: $^O ne 'darwin'



=== TEST 2: PCRE MAP_JIT workaround on macOS logs only once per flag
--- init_by_lua_block
    jit.off() -- must disable in this test or logs will be fuzzy

    for i = 1, 2 do
        ngx.re.match("c", "test", "j")
    end

    for i = 1, 2 do
        ngx.re.match("c", "test", "o")
    end

    for i = 1, 2 do
        ngx.re.match("c", "test", "jo")
    end
--- config
    location /re {
        content_by_lua_block {
            ngx.say(ngx.re.sub("c", "a", "b", ""))
            ngx.say(ngx.re.sub("c", "a", "b", "jo"))
        }
    }
--- request
GET /re
--- response_body
c0
c0
--- grep_error_log eval
qr/parse_regex_opts\(\): .*? disabled in init phase under macOS/
--- grep_error_log_out eval
qr/\A(?:parse_regex_opts\(\): regex compilation (?:cache )?disabled in init phase under macOS\s*){4}\z/
--- no_error_log
[error]
--- skip_eval
4: $^O ne 'darwin'



=== TEST 3: PCRE MAP_JIT workaround is reverted after init phase
--- init_by_lua_block
    ngx.re.match("c", "test", "jo")
--- config
    location /re {
        content_by_lua_block {
            ngx.say(ngx.re.sub("c", "a", "b", ""))
            ngx.say(ngx.re.sub("c", "a", "b", "jo"))
        }
    }
--- request
GET /re
--- response_body
c0
c0
--- no_error_log
[error]
disabled in init phase under macOS, client:
--- skip_eval
4: $^O ne 'darwin'



=== TEST 4: PCRE MAP_JIT workaround is not in effect under other OSs
--- init_by_lua_block
    ngx.re.match("c", "test", "jo")
--- config
    location /re {
        content_by_lua_block {
            ngx.say(ngx.re.sub("c", "a", "b", ""))
            ngx.say(ngx.re.sub("c", "a", "b", "jo"))
        }
    }
--- request
GET /re
--- response_body
c0
c0
--- no_error_log
[error]
disabled in init phase under macOS
--- skip_eval
4: $^O ne 'linux'



=== TEST 5: bug: sub incorrectly dropped the last character
--- config
    location /re {
        content_by_lua_block {
            local s, n = ngx.re.sub("abcd", "(?<=c)", ".")
            ngx.say(s)
            ngx.say(n)
        }
    }
--- request
    GET /re
--- response_body
abc.d
1



=== TEST 6: bug: sub incorrectly dropped the last character(replace function)
--- config
    location /re {
        content_by_lua_block {
            local function repl(m)
                return "[" .. m[0] .. "]"
            end
            local s, n = ngx.re.sub("abcd", "(?<=c)", repl)
            ngx.say(s)
            ngx.say(n)
        }
    }
--- request
    GET /re
--- response_body
abc[]d
1
