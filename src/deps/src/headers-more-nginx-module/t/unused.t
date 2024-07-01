# vi:filetype=

use lib 'lib';
use Test::Nginx::Socket;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4 + 2);

#master_on();
#workers(2);
log_level("warn");
no_diff;

run_tests();

__DATA__

=== TEST 1: used output filter
--- config
    location /foo {
        echo hi;
        more_set_headers "Foo: bar";
    }
--- request
    GET /foo
--- response_headers
Foo: bar
--- response_body
hi
--- error_log
headers more header filter
--- no_error_log
[error]
--- log_level: debug



=== TEST 2: unused output filter (none)
--- config
    location /foo {
        echo hi;
    }
--- request
    GET /foo
--- response_body
hi
--- no_error_log
headers more header filter
[error]
--- log_level: debug



=== TEST 3: unused output filter (with more_set_input_headers only)
--- config
    location /foo {
        more_set_input_headers "Foo: bar";
        echo hi;
    }
--- request
    GET /foo
--- response_body
hi
--- no_error_log
headers more header filter
[error]
--- log_level: debug



=== TEST 4: used rewrite handler
--- config
    location /foo {
        more_set_input_headers "Foo: bar";
        echo hi;
    }
--- request
    GET /foo
--- response_body
hi
--- error_log
headers more rewrite handler
--- no_error_log
[error]
--- log_level: debug



=== TEST 5: unused rewrite handler (none)
--- config
    location /foo {
        #more_set_input_headers "Foo: bar";
        echo hi;
    }
--- request
    GET /foo
--- response_body
hi
--- no_error_log
headers more rewrite handler
[error]
--- log_level: debug



=== TEST 6: unused rewrite handler (with output header filters)
--- config
    location /foo {
        #more_set_input_headers "Foo: bar";
        echo hi;
        more_set_headers "Foo: bar";
    }
--- request
    GET /foo
--- response_headers
Foo: bar
--- response_body
hi
--- no_error_log
headers more rewrite handler
[error]
--- log_level: debug



=== TEST 7: multiple http {} blocks (filter)
This test case won't run with nginx 1.9.3+ since duplicate http {} blocks
have been prohibited since then.
--- SKIP
--- config
    location /foo {
        echo hi;
        more_set_headers 'Foo: bar';
    }
--- post_main_config
    http {
    }

--- request
    GET /foo
--- response_body
hi
--- response_headers
Foo: bar
--- no_error_log
[error]
--- error_log
headers more header filter
--- log_level: debug



=== TEST 8: multiple http {} blocks (handler)
This test case won't run with nginx 1.9.3+ since duplicate http {} blocks
have been prohibited since then.
--- SKIP
--- config
    location /foo {
        more_set_input_headers 'Foo: bar';
        echo $http_foo;
    }
--- post_main_config
    http {
    }

--- request
    GET /foo
--- response_body
bar
--- no_error_log
headers more header handler
[error]
--- log_level: debug
