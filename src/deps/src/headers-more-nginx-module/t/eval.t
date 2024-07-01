# vi:filetype=

use lib 'lib';
use Test::Nginx::Socket; # 'no_plan';

repeat_each(3);

plan tests => repeat_each() * 2 * blocks();

#no_long_string();
#no_diff;

run_tests();

__DATA__

=== TEST 1: set request header at client side
--- config
    location /foo {
        eval_subrequest_in_memory off;
        eval_override_content_type text/plain;
        eval $res {
            echo -n 1;
        }
        #echo "[$res]";
        if ($res = '1') {
            more_set_input_headers 'Foo: Bar';
            echo "OK";
            break;
        }
        echo "NOT OK";
    }
--- request
    GET /foo
--- response_body
OK
