# vi:ft=

use lib 'lib';
use Test::Nginx::Socket; # 'no_plan';

plan tests => 9;

no_diff;

run_tests();

__DATA__

=== TEST 1: vars
--- config
    location /foo {
        echo hi;
        set $val 'hello, world';
        more_set_headers 'X-Foo: $val';
    }
--- request
    GET /foo
--- response_headers
X-Foo: hello, world
--- response_body
hi



=== TEST 2: vars in both key and val
--- config
    location /foo {
        echo hi;
        set $val 'hello, world';
        more_set_headers '$val: $val';
    }
--- request
    GET /foo
--- response_headers
$val: hello, world
--- response_body
hi



=== TEST 3: vars in input header directives
--- config
    location /foo {
        set $val 'dog';
        more_set_input_headers 'Host: $val';
        echo $host;
    }
--- request
    GET /foo
--- response_body
dog
--- response_headers
Host:
