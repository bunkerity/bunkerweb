# vim:set ft= ts=4 sw=4 et fdm=marker:

use lib 'lib';
use Test::Nginx::Socket;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (4 * blocks());

#no_diff();
no_long_string();

run_tests();

__DATA__

=== TEST 1: clear cookie (with existing cookies)
--- config
    location /t {
        more_clear_input_headers Cookie;
        echo "Cookie foo: $cookie_foo";
        echo "Cookie baz: $cookie_baz";
        echo "Cookie: $http_cookie";
    }
--- request
GET /t
--- more_headers
Cookie: foo=bar
Cookie: baz=blah

--- stap
F(ngx_http_headers_more_exec_input_cmd) {
    printf("rewrite: cookies: %d\n", $r->headers_in->cookies->nelts)
}

F(ngx_http_core_content_phase) {
    printf("content: cookies: %d\n", $r->headers_in->cookies->nelts)
}

--- stap_out
rewrite: cookies: 2
content: cookies: 0

--- response_body
Cookie foo: 
Cookie baz: 
Cookie: 

--- no_error_log
[error]



=== TEST 2: clear cookie (without existing cookies)
--- config
    location /t {
        more_clear_input_headers Cookie;
        echo "Cookie foo: $cookie_foo";
        echo "Cookie baz: $cookie_baz";
        echo "Cookie: $http_cookie";
    }
--- request
GET /t

--- stap
F(ngx_http_headers_more_exec_input_cmd) {
    printf("rewrite: cookies: %d\n", $r->headers_in->cookies->nelts)
}

F(ngx_http_core_content_phase) {
    printf("content: cookies: %d\n", $r->headers_in->cookies->nelts)
}

--- stap_out
rewrite: cookies: 0
content: cookies: 0

--- response_body
Cookie foo: 
Cookie baz: 
Cookie: 

--- no_error_log
[error]



=== TEST 3: set one custom cookie (with existing cookies)
--- config
    location /t {
        more_set_input_headers "Cookie: boo=123";
        echo "Cookie foo: $cookie_foo";
        echo "Cookie baz: $cookie_baz";
        echo "Cookie boo: $cookie_boo";
        echo "Cookie: $http_cookie";
    }
--- request
GET /t
--- more_headers
Cookie: foo=bar
Cookie: baz=blah

--- stap
F(ngx_http_headers_more_exec_input_cmd) {
    printf("rewrite: cookies: %d\n", $r->headers_in->cookies->nelts)
}

F(ngx_http_core_content_phase) {
    printf("content: cookies: %d\n", $r->headers_in->cookies->nelts)
}

--- stap_out
rewrite: cookies: 2
content: cookies: 1

--- response_body
Cookie foo: 
Cookie baz: 
Cookie boo: 123
Cookie: boo=123

--- no_error_log
[error]



=== TEST 4: set one custom cookie (without existing cookies)
--- config
    location /t {
        more_set_input_headers "Cookie: boo=123";
        echo "Cookie foo: $cookie_foo";
        echo "Cookie baz: $cookie_baz";
        echo "Cookie boo: $cookie_boo";
        echo "Cookie: $http_cookie";
    }
--- request
GET /t

--- stap
F(ngx_http_headers_more_exec_input_cmd) {
    printf("rewrite: cookies: %d\n", $r->headers_in->cookies->nelts)
}

F(ngx_http_core_content_phase) {
    printf("content: cookies: %d\n", $r->headers_in->cookies->nelts)
}

--- stap_out
rewrite: cookies: 0
content: cookies: 1

--- response_body
Cookie foo: 
Cookie baz: 
Cookie boo: 123
Cookie: boo=123

--- no_error_log
[error]



=== TEST 5: for bad requests causing segfaults when setting & getting multi-value headers
--- config
    error_page 400 = /err;

    location = /err {
        more_set_input_headers "Cookie: foo=bar";
        echo -n $cookie_foo;
        echo ok;
    }
--- raw_request
GeT / HTTP/1.1
--- response_body
ok
--- no_error_log
[warn]
[error]
--- no_check_leak
