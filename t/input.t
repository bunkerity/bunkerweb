# vi:filetype=

use lib 'lib';
use Test::Nginx::Socket; # 'no_plan';

repeat_each(2);

plan tests => repeat_each() * 128;

no_long_string();
#no_diff;

run_tests();

__DATA__

=== TEST 1: set request header at client side
--- config
    location /foo {
        #more_set_input_headers 'X-Foo: howdy';
        echo $http_x_foo;
    }
--- request
    GET /foo
--- more_headers
X-Foo: blah
--- response_headers
! X-Foo
--- response_body
blah



=== TEST 2: set request header at client side and rewrite it
--- config
    location /foo {
        more_set_input_headers 'X-Foo: howdy';
        echo $http_x_foo;
    }
--- request
    GET /foo
--- more_headers
X-Foo: blah
--- response_headers
! X-Foo
--- response_body
howdy



=== TEST 3: rewrite content length
--- config
    location /bar {
        more_set_input_headers 'Content-Length: 2048';
        echo_read_request_body;
        echo_request_body;
    }
--- request eval
"POST /bar\n" .
"a" x 4096
--- response_body eval
"a" x 2048
--- timeout: 15



=== TEST 4: try to rewrite content length using the rewrite module
Thisshould not take effect ;)
--- config
    location /bar {
        set $http_content_length 2048;
        echo_read_request_body;
        echo_request_body;
    }
--- request eval
"POST /bar\n" .
"a" x 4096
--- response_body eval
"a" x 4096



=== TEST 5: rewrite host and user-agent
--- config
    location /bar {
        more_set_input_headers 'Host: foo' 'User-Agent: blah';
        echo "Host: $host";
        echo "User-Agent: $http_user_agent";
    }
--- request
GET /bar
--- response_body
Host: foo
User-Agent: blah



=== TEST 6: clear host and user-agent
$host always has a default value and cannot be really cleared.
--- config
    location /bar {
        more_clear_input_headers 'Host: foo' 'User-Agent: blah';
        echo "Host: $host";
        echo "Host (2): $http_host";
        echo "User-Agent: $http_user_agent";
    }
--- request
GET /bar
--- response_body
Host: localhost
Host (2): 
User-Agent: 



=== TEST 7: clear host and user-agent (the other way)
--- config
    location /bar {
        more_set_input_headers 'Host:' 'User-Agent:' 'X-Foo:';
        echo "Host: $host";
        echo "User-Agent: $http_user_agent";
        echo "X-Foo: $http_x_foo";
    }
--- request
GET /bar
--- more_headers
X-Foo: bar
--- response_body
Host: localhost
User-Agent: 
X-Foo: 



=== TEST 8: clear content-length
--- config
    location /bar {
        more_set_input_headers 'Content-Length: ';
        echo "Content-Length: $http_content_length";
    }
--- request
POST /bar
hello
--- more_headers
--- response_body
Content-Length: 



=== TEST 9: clear content-length (the other way)
--- config
    location /bar {
        more_clear_input_headers 'Content-Length: ';
        echo "Content-Length: $http_content_length";
    }
--- request
POST /bar
hello
--- more_headers
--- response_body
Content-Length: 



=== TEST 10: rewrite type
--- config
    location /bar {
        more_set_input_headers 'Content-Type: text/css';
        echo "Content-Type: $content_type";
    }
--- request
POST /bar
hello
--- more_headers
Content-Type: text/plain
--- response_body
Content-Type: text/css



=== TEST 11: clear type
--- config
    location /bar {
        more_set_input_headers 'Content-Type:';
        echo "Content-Type: $content_type";
    }
--- request
POST /bar
hello
--- more_headers
Content-Type: text/plain
--- response_body
Content-Type: 



=== TEST 12: clear type (the other way)
--- config
    location /bar {
        more_clear_input_headers 'Content-Type:foo';
        echo "Content-Type: $content_type";
    }
--- request
POST /bar
hello
--- more_headers
Content-Type: text/plain
--- response_body
Content-Type: 



=== TEST 13: add type constraints
--- config
    location /bar {
        more_set_input_headers -t 'text/plain' 'X-Blah:yay';
        echo $http_x_blah;
    }
--- request
POST /bar
hello
--- more_headers
Content-Type: text/plain
--- response_body
yay



=== TEST 14: add type constraints (not matched)
--- config
    location /bar {
        more_set_input_headers -t 'text/plain' 'X-Blah:yay';
        echo $http_x_blah;
    }
--- request
POST /bar
hello
--- more_headers
Content-Type: text/css
--- response_body eval: "\n"



=== TEST 15: add type constraints (OR'd)
--- config
    location /bar {
        more_set_input_headers -t 'text/plain text/css' 'X-Blah:yay';
        echo $http_x_blah;
    }
--- request
POST /bar
hello
--- more_headers
Content-Type: text/css
--- response_body
yay



=== TEST 16: add type constraints (OR'd)
--- config
    location /bar {
        more_set_input_headers -t 'text/plain text/css' 'X-Blah:yay';
        echo $http_x_blah;
    }
--- request
POST /bar
hello
--- more_headers
Content-Type: text/plain
--- response_body
yay



=== TEST 17: add type constraints (OR'd) (not matched)
--- config
    location /bar {
        more_set_input_headers -t 'text/plain text/css' 'X-Blah:yay';
        echo $http_x_blah;
    }
--- request
POST /bar
hello
--- more_headers
Content-Type: text/html
--- response_body eval: "\n"



=== TEST 18: mix input and output cmds
--- config
    location /bar {
        more_set_input_headers 'X-Blah:yay';
        more_set_headers 'X-Blah:hiya';
        echo $http_x_blah;
    }
--- request
GET /bar
--- response_headers
X-Blah: hiya
--- response
yay



=== TEST 19: set request header at client side and replace
--- config
    location /foo {
        more_set_input_headers -r 'X-Foo: howdy';
        echo $http_x_foo;
    }
--- request
    GET /foo
--- more_headers
X-Foo: blah
--- response_headers
! X-Foo
--- response_body
howdy



=== TEST 20: do no set request header at client, so no replace with -r option
--- config
    location /foo {
        more_set_input_headers -r 'X-Foo: howdy';
        echo "empty_header:" $http_x_foo;
    }
--- request
    GET /foo
--- response_headers
! X-Foo
--- response_body
empty_header: 



=== TEST 21: clear input headers
--- config
    location /foo {
        set $val 'dog';

        more_clear_input_headers 'User-Agent';

        proxy_pass http://127.0.0.1:$server_port/proxy;
    }
    location /proxy {
        echo -n $echo_client_request_headers;
    }
--- request
    GET /foo
--- more_headers
User-Agent: my-sock
--- response_body eval
"GET /proxy HTTP/1.0\r
Host: 127.0.0.1:\$ServerPort\r
Connection: close\r
\r
"
--- skip_nginx: 3: < 0.7.46



=== TEST 22: clear input headers
--- config
    location /foo {
        more_clear_input_headers 'User-Agent';

        proxy_pass http://127.0.0.1:$server_port/proxy;
    }
    location /proxy {
        echo -n $echo_client_request_headers;
    }
--- request
    GET /foo
--- response_body eval
"GET /proxy HTTP/1.0\r
Host: 127.0.0.1:\$ServerPort\r
Connection: close\r
\r
"
--- skip_nginx: 3: < 0.7.46



=== TEST 23: clear input headers
--- config
    location /foo {
        more_clear_input_headers 'X-Foo19';
        more_clear_input_headers 'X-Foo20';
        more_clear_input_headers 'X-Foo21';

        proxy_pass http://127.0.0.1:$server_port/proxy;
    }
    location /proxy {
        echo -n $echo_client_request_headers;
    }
--- request
    GET /foo
--- more_headers eval
my $s;
for my $i (3..21) {
    $s .= "X-Foo$i: $i\n";
}
$s;
--- response_body eval
"GET /proxy HTTP/1.0\r
Host: 127.0.0.1:\$ServerPort\r
Connection: close\r
X-Foo3: 3\r
X-Foo4: 4\r
X-Foo5: 5\r
X-Foo6: 6\r
X-Foo7: 7\r
X-Foo8: 8\r
X-Foo9: 9\r
X-Foo10: 10\r
X-Foo11: 11\r
X-Foo12: 12\r
X-Foo13: 13\r
X-Foo14: 14\r
X-Foo15: 15\r
X-Foo16: 16\r
X-Foo17: 17\r
X-Foo18: 18\r
\r
"
--- skip_nginx: 3: < 0.7.46



=== TEST 24: Accept-Encoding
--- config
    location /bar {
        default_type 'text/plain';
        more_set_input_headers 'Accept-Encoding: gzip';
        gzip on;
        gzip_min_length  1;
        gzip_buffers     4 8k;
        gzip_types       text/plain;
    }
--- user_files
">>> bar
" . ("hello" x 512)
--- request
GET /bar
--- response_headers
Content-Encoding: gzip
--- response_body_like: .



=== TEST 25: rewrite + set request header
--- config
    location /t {
        rewrite ^ /foo last;
    }

    location /foo {
        more_set_input_headers 'X-Foo: howdy';
        proxy_pass http://127.0.0.1:$server_port/echo;
    }

    location /echo {
        echo "X-Foo: $http_x_foo";
    }
--- request
    GET /foo
--- response_headers
! X-Foo
--- response_body
X-Foo: howdy



=== TEST 26: clear_header should clear all the instances of the user custom header
--- config
    location = /t {
        more_clear_input_headers Foo;

        proxy_pass http://127.0.0.1:$server_port/echo;
    }

    location = /echo {
        echo "Foo: [$http_foo]";
        echo "Test-Header: [$http_test_header]";
    }
--- request
GET /t
--- more_headers
Foo: foo
Foo: bah
Test-Header: 1
--- response_body
Foo: []
Test-Header: [1]



=== TEST 27: clear_header should clear all the instances of the builtin header
--- config
    location = /t {
        more_clear_input_headers Content-Type;

        proxy_pass http://127.0.0.1:$server_port/echo;
    }

    location = /echo {
        echo "Content-Type: [$http_content_type]";
        echo "Test-Header: [$http_test_header]";
        #echo $echo_client_request_headers;
    }
--- request
GET /t
--- more_headers
Content-Type: foo
Content-Type: bah
Test-Header: 1
--- response_body
Content-Type: []
Test-Header: [1]



=== TEST 28: Converting POST to GET - clearing headers (bug found by Matthieu Tourne, 411 error page)
--- config
    location /t {
        more_clear_input_headers Content-Type;
        more_clear_input_headers Content-Length;

        #proxy_pass http://127.0.0.1:8888;
        proxy_pass http://127.0.0.1:$server_port/back;
    }

    location /back {
        echo $echo_client_request_headers;
    }
--- request
POST /t
hello world
--- more_headers
Content-Type: application/ocsp-request
Test-Header: 1
--- response_body_like eval
qr/Connection: close\r
Test-Header: 1\r
\r
$/
--- no_error_log
[error]



=== TEST 29: clear_header() does not duplicate subsequent headers (old bug)
--- config
    location = /t {
        more_clear_input_headers Foo;

        proxy_pass http://127.0.0.1:$server_port/echo;
    }

    location = /echo {
        echo $echo_client_request_headers;
    }
--- request
GET /t
--- more_headers
Bah: bah
Foo: foo
Test-Header: 1
Foo1: foo1
Foo2: foo2
Foo3: foo3
Foo4: foo4
Foo5: foo5
Foo6: foo6
Foo7: foo7
Foo8: foo8
Foo9: foo9
Foo10: foo10
Foo11: foo11
Foo12: foo12
Foo13: foo13
Foo14: foo14
Foo15: foo15
Foo16: foo16
Foo17: foo17
Foo18: foo18
Foo19: foo19
Foo20: foo20
Foo21: foo21
Foo22: foo22
--- response_body_like eval
qr/Bah: bah\r
Test-Header: 1\r
Foo1: foo1\r
Foo2: foo2\r
Foo3: foo3\r
Foo4: foo4\r
Foo5: foo5\r
Foo6: foo6\r
Foo7: foo7\r
Foo8: foo8\r
Foo9: foo9\r
Foo10: foo10\r
Foo11: foo11\r
Foo12: foo12\r
Foo13: foo13\r
Foo14: foo14\r
Foo15: foo15\r
Foo16: foo16\r
Foo17: foo17\r
Foo18: foo18\r
Foo19: foo19\r
Foo20: foo20\r
Foo21: foo21\r
Foo22: foo22\r
/



=== TEST 30: clear input header (just more than 20 headers)
--- config
    location = /t {
        more_clear_input_headers "R";
        proxy_pass http://127.0.0.1:$server_port/back;
        proxy_set_header Host foo;
        #proxy_pass http://127.0.0.1:1234/back;
    }

    location = /back {
        echo -n $echo_client_request_headers;
    }
--- request
GET /t
--- more_headers eval
my $s = "User-Agent: curl\n";

for my $i ('a' .. 'r') {
    $s .= uc($i) . ": " . "$i\n"
}
$s
--- response_body eval
"GET /back HTTP/1.0\r
Host: foo\r
Connection: close\r
User-Agent: curl\r
A: a\r
B: b\r
C: c\r
D: d\r
E: e\r
F: f\r
G: g\r
H: h\r
I: i\r
J: j\r
K: k\r
L: l\r
M: m\r
N: n\r
O: o\r
P: p\r
Q: q\r
\r
"



=== TEST 31: clear input header (just more than 20 headers, and add more)
--- config
    location = /t {
        more_clear_input_headers R;
        more_set_input_headers "foo-1: 1" "foo-2: 2" "foo-3: 3" "foo-4: 4"
            "foo-5: 5" "foo-6: 6" "foo-7: 7" "foo-8: 8" "foo-9: 9"
            "foo-10: 10" "foo-11: 11" "foo-12: 12" "foo-13: 13"
            "foo-14: 14" "foo-15: 15" "foo-16: 16" "foo-17: 17" "foo-18: 18"
            "foo-19: 19" "foo-20: 20" "foo-21: 21";

        proxy_pass http://127.0.0.1:$server_port/back;
        proxy_set_header Host foo;
        #proxy_pass http://127.0.0.1:1234/back;
    }

    location = /back {
        echo -n $echo_client_request_headers;
    }
--- request
GET /t
--- more_headers eval
my $s = "User-Agent: curl\n";

for my $i ('a' .. 'r') {
    $s .= uc($i) . ": " . "$i\n"
}
$s
--- response_body eval
"GET /back HTTP/1.0\r
Host: foo\r
Connection: close\r
User-Agent: curl\r
A: a\r
B: b\r
C: c\r
D: d\r
E: e\r
F: f\r
G: g\r
H: h\r
I: i\r
J: j\r
K: k\r
L: l\r
M: m\r
N: n\r
O: o\r
P: p\r
Q: q\r
foo-1: 1\r
foo-2: 2\r
foo-3: 3\r
foo-4: 4\r
foo-5: 5\r
foo-6: 6\r
foo-7: 7\r
foo-8: 8\r
foo-9: 9\r
foo-10: 10\r
foo-11: 11\r
foo-12: 12\r
foo-13: 13\r
foo-14: 14\r
foo-15: 15\r
foo-16: 16\r
foo-17: 17\r
foo-18: 18\r
foo-19: 19\r
foo-20: 20\r
foo-21: 21\r
\r
"



=== TEST 32: clear input header (just more than 21 headers)
--- config
    location = /t {
        more_clear_input_headers R Q;
        proxy_pass http://127.0.0.1:$server_port/back;
        proxy_set_header Host foo;
        #proxy_pass http://127.0.0.1:1234/back;
    }

    location = /back {
        echo -n $echo_client_request_headers;
    }
--- request
GET /t
--- more_headers eval
my $s = "User-Agent: curl\nBah: bah\n";

for my $i ('a' .. 'r') {
    $s .= uc($i) . ": " . "$i\n"
}
$s
--- response_body eval
"GET /back HTTP/1.0\r
Host: foo\r
Connection: close\r
User-Agent: curl\r
Bah: bah\r
A: a\r
B: b\r
C: c\r
D: d\r
E: e\r
F: f\r
G: g\r
H: h\r
I: i\r
J: j\r
K: k\r
L: l\r
M: m\r
N: n\r
O: o\r
P: p\r
\r
"



=== TEST 33: clear input header (just more than 21 headers)
--- config
    location = /t {
        more_clear_input_headers R Q;
        more_set_input_headers "foo-1: 1" "foo-2: 2" "foo-3: 3" "foo-4: 4"
            "foo-5: 5" "foo-6: 6" "foo-7: 7" "foo-8: 8" "foo-9: 9"
            "foo-10: 10" "foo-11: 11" "foo-12: 12" "foo-13: 13"
            "foo-14: 14" "foo-15: 15" "foo-16: 16" "foo-17: 17" "foo-18: 18"
            "foo-19: 19" "foo-20: 20" "foo-21: 21";

        proxy_pass http://127.0.0.1:$server_port/back;
        proxy_set_header Host foo;
        #proxy_pass http://127.0.0.1:1234/back;
    }

    location = /back {
        echo -n $echo_client_request_headers;
    }
--- request
GET /t
--- more_headers eval
my $s = "User-Agent: curl\nBah: bah\n";

for my $i ('a' .. 'r') {
    $s .= uc($i) . ": " . "$i\n"
}
$s
--- response_body eval
"GET /back HTTP/1.0\r
Host: foo\r
Connection: close\r
User-Agent: curl\r
Bah: bah\r
A: a\r
B: b\r
C: c\r
D: d\r
E: e\r
F: f\r
G: g\r
H: h\r
I: i\r
J: j\r
K: k\r
L: l\r
M: m\r
N: n\r
O: o\r
P: p\r
foo-1: 1\r
foo-2: 2\r
foo-3: 3\r
foo-4: 4\r
foo-5: 5\r
foo-6: 6\r
foo-7: 7\r
foo-8: 8\r
foo-9: 9\r
foo-10: 10\r
foo-11: 11\r
foo-12: 12\r
foo-13: 13\r
foo-14: 14\r
foo-15: 15\r
foo-16: 16\r
foo-17: 17\r
foo-18: 18\r
foo-19: 19\r
foo-20: 20\r
foo-21: 21\r
\r
"



=== TEST 34: clear X-Real-IP
--- config
    location /t {
        more_clear_input_headers X-Real-IP;
        echo "X-Real-IP: $http_x_real_ip";
    }
--- request
GET /t
--- more_headers
X-Real-IP: 8.8.8.8

--- stap
F(ngx_http_headers_more_exec_input_cmd) {
    if (@defined($r->headers_in->x_real_ip) && $r->headers_in->x_real_ip) {
        printf("rewrite: x-real-ip: %s\n",
               user_string_n($r->headers_in->x_real_ip->value->data,
                             $r->headers_in->x_real_ip->value->len))
    } else {
        println("rewrite: no x-real-ip")
    }
}

F(ngx_http_core_content_phase) {
    if (@defined($r->headers_in->x_real_ip) && $r->headers_in->x_real_ip) {
        printf("content: x-real-ip: %s\n",
               user_string_n($r->headers_in->x_real_ip->value->data,
                             $r->headers_in->x_real_ip->value->len))
    } else {
        println("content: no x-real-ip")
    }
}

--- stap_out
rewrite: x-real-ip: 8.8.8.8
content: no x-real-ip

--- response_body
X-Real-IP: 

--- no_error_log
[error]



=== TEST 35: set custom X-Real-IP
--- config
    location /t {
        more_set_input_headers "X-Real-IP: 8.8.4.4";
        echo "X-Real-IP: $http_x_real_ip";
    }
--- request
GET /t

--- stap
F(ngx_http_headers_more_exec_input_cmd) {
    if (@defined($r->headers_in->x_real_ip) && $r->headers_in->x_real_ip) {
        printf("rewrite: x-real-ip: %s\n",
               user_string_n($r->headers_in->x_real_ip->value->data,
                             $r->headers_in->x_real_ip->value->len))
    } else {
        println("rewrite: no x-real-ip")
    }

}

F(ngx_http_core_content_phase) {
    if (@defined($r->headers_in->x_real_ip) && $r->headers_in->x_real_ip) {
        printf("content: x-real-ip: %s\n",
               user_string_n($r->headers_in->x_real_ip->value->data,
                             $r->headers_in->x_real_ip->value->len))
    } else {
        println("content: no x-real-ip")
    }
}

--- stap_out
rewrite: no x-real-ip
content: x-real-ip: 8.8.4.4

--- response_body
X-Real-IP: 8.8.4.4

--- no_error_log
[error]



=== TEST 36: clear Via
--- config
    location /t {
        more_clear_input_headers Via;
        echo "Via: $http_via";
    }
--- request
GET /t
--- more_headers
Via: 1.0 fred, 1.1 nowhere.com (Apache/1.1)

--- stap
F(ngx_http_headers_more_exec_input_cmd) {
    if (@defined($r->headers_in->via) && $r->headers_in->via) {
        printf("rewrite: via: %s\n",
               user_string_n($r->headers_in->via->value->data,
                             $r->headers_in->via->value->len))
    } else {
        println("rewrite: no via")
    }
}

F(ngx_http_core_content_phase) {
    if (@defined($r->headers_in->via) && $r->headers_in->via) {
        printf("content: via: %s\n",
               user_string_n($r->headers_in->via->value->data,
                             $r->headers_in->via->value->len))
    } else {
        println("content: no via")
    }
}

--- stap_out
rewrite: via: 1.0 fred, 1.1 nowhere.com (Apache/1.1)
content: no via

--- response_body
Via: 

--- no_error_log
[error]



=== TEST 37: set custom Via
--- config
    location /t {
        more_set_input_headers "Via: 1.0 fred, 1.1 nowhere.com (Apache/1.1)";
        echo "Via: $http_via";
    }
--- request
GET /t

--- stap
F(ngx_http_headers_more_exec_input_cmd) {
    if (@defined($r->headers_in->via) && $r->headers_in->via) {
        printf("rewrite: via: %s\n",
               user_string_n($r->headers_in->via->value->data,
                             $r->headers_in->via->value->len))
    } else {
        println("rewrite: no via")
    }

}

F(ngx_http_core_content_phase) {
    if (@defined($r->headers_in->via) && $r->headers_in->via) {
        printf("content: via: %s\n",
               user_string_n($r->headers_in->via->value->data,
                             $r->headers_in->via->value->len))
    } else {
        println("content: no via")
    }
}

--- stap_out
rewrite: no via
content: via: 1.0 fred, 1.1 nowhere.com (Apache/1.1)

--- response_body
Via: 1.0 fred, 1.1 nowhere.com (Apache/1.1)

--- no_error_log
[error]



=== TEST 38: HTTP 0.9 (set)
--- config
    location /foo {
        more_set_input_headers 'X-Foo: howdy';
        echo "x-foo: $http_x_foo";
    }
--- raw_request eval
"GET /foo\r\n"
--- response_headers
! X-Foo
--- response_body
x-foo: 
--- http09



=== TEST 39: HTTP 0.9 (clear)
--- config
    location /foo {
        more_clear_input_headers 'X-Foo';
        echo "x-foo: $http_x_foo";
    }
--- raw_request eval
"GET /foo\r\n"
--- response_headers
! X-Foo
--- response_body
x-foo: 
--- http09



=== TEST 40: Host header with port and $host
--- config
    location /bar {
        more_set_input_headers 'Host: agentzh.org:1984';
        echo "host var: $host";
        echo "http_host var: $http_host";
    }
--- request
GET /bar
--- response_body
host var: agentzh.org
http_host var: agentzh.org:1984



=== TEST 41: Host header with upper case letters and $host
--- config
    location /bar {
        more_set_input_headers 'Host: agentZH.org:1984';
        echo "host var: $host";
        echo "http_host var: $http_host";
    }
--- request
GET /bar
--- response_body
host var: agentzh.org
http_host var: agentZH.org:1984



=== TEST 42: clear all and re-insert
--- config
    location = /t {
        more_clear_input_headers Host Connection Cache-Control Accept
                                 User-Agent Accept-Encoding Accept-Language
                                 Cookie;

        more_set_input_headers "Host: a" "Connection: b" "Cache-Control: c"
                               "Accept: d" "User-Agent: e" "Accept-Encoding: f"
                               "Accept-Language: g" "Cookie: h";

        more_clear_input_headers Host Connection Cache-Control Accept
                                 User-Agent Accept-Encoding Accept-Language
                                 Cookie;

        more_set_input_headers "Host: a" "Connection: b" "Cache-Control: c"
                               "Accept: d" "User-Agent: e" "Accept-Encoding: f"
                               "Accept-Language: g" "Cookie: h";

        echo ok;
    }

--- raw_request eval
"GET /t HTTP/1.1\r
Host: localhost\r
Connection: close\r
Cache-Control: max-age=0\r
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8\r
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36\r
Accept-Encoding: gzip,deflate,sdch\r
Accept-Language: en-US,en;q=0.8\r
Cookie: test=cookie;\r
\r
"
--- response_body
ok
--- no_error_log
[error]



=== TEST 43: more_set_input_header does not override request headers with multiple values
--- config
    #lua_code_cache off;
    location = /t {
        more_set_input_headers "AAA: 111";

        content_by_lua '
            local headers = ngx.req.get_headers()
            ngx.say(headers["AAA"])
        ';
    }
--- request
GET /t
--- more_headers
AAA: 123
AAA: 456
AAA: 678

--- response_body
111
--- no_error_log
[error]



=== TEST 44: clear If-Unmodified-Since req header
--- config
    location = /t {
        more_clear_input_headers 'If-Unmodified-Since';
        content_by_lua '
            ngx.header["Last-Modified"] = "Tue, 30 Jun 2011 12:16:36 GMT"
            ngx.say("If-Unmodified-Since: ", ngx.var.http_if_unmodified_since)
        ';
    }
--- request
GET /t
--- more_headers
If-Unmodified-Since: Tue, 28 Jun 2011 12:16:36 GMT
--- response_body
If-Unmodified-Since: nil
--- no_error_log
[error]



=== TEST 45: clear If-Match req header
--- config
    location = /t {
        more_clear_input_headers 'If-Match';
        echo "If-Match: $http_if_match";
    }
--- request
GET /t
--- more_headers
If-Match: abc
--- response_body
If-Match: 
--- no_error_log
[error]



=== TEST 46: clear If-None-Match req header
--- config
    location = /t {
        more_clear_input_headers 'If-None-Match';
        echo "If-None-Match: $http_if_none_match";
    }
--- request
GET /t
--- more_headers
If-None-Match: *
--- response_body
If-None-Match: 
--- no_error_log
[error]



=== TEST 47: set the Destination request header for WebDav
--- config
    location = /a.txt {
        more_set_input_headers "Destination: /b.txt";
        dav_methods MOVE;
        dav_access            all:rw;
        root                  html;
    }

--- user_files
>>> a.txt
hello, world!

--- request
MOVE /a.txt

--- response_body
--- no_error_log
client sent no "Destination" header
[error]
--- error_code: 204



=== TEST 48: more_set_input_headers + X-Forwarded-For
--- config
    location = /t {
        more_set_input_headers "X-Forwarded-For: 8.8.8.8";
        proxy_pass http://127.0.0.1:$server_port/back;
        proxy_set_header Foo $proxy_add_x_forwarded_for;
    }

    location = /back {
        echo "Foo: $http_foo";
    }

--- request
GET /t

--- response_body
Foo: 8.8.8.8, 127.0.0.1
--- no_error_log
[error]



=== TEST 49: more_clear_input_headers + X-Forwarded-For
--- config
    location = /t {
        more_clear_input_headers "X-Forwarded-For";
        proxy_pass http://127.0.0.1:$server_port/back;
        proxy_set_header Foo $proxy_add_x_forwarded_for;
    }

    location = /back {
        echo "Foo: $http_foo";
    }

--- request
GET /t

--- more_headers
X-Forwarded-For: 8.8.8.8
--- response_body
Foo: 127.0.0.1
--- no_error_log
[error]



=== TEST 50: clear input headers with wildcard
--- config
    location /hello {
        more_clear_input_headers 'X-Hidden-*';
        content_by_lua '
            ngx.say("X-Hidden-One: ", ngx.var.http_x_hidden_one)
            ngx.say("X-Hidden-Two: ", ngx.var.http_x_hidden_two)
        ';
    }
--- request
    GET /hello
--- more_headers
X-Hidden-One: i am hidden
X-Hidden-Two: me 2
--- response_body
X-Hidden-One: nil
X-Hidden-Two: nil



=== TEST 51: make sure wildcard doesn't affect more_set_input_headers
--- config
    location /hello {
        more_set_input_headers 'X-Hidden-*: lol';
        content_by_lua '
            ngx.say("X-Hidden-One: ", ngx.var.http_x_hidden_one)
            ngx.say("X-Hidden-Two: ", ngx.var.http_x_hidden_two)
        ';
    }
--- request
    GET /hello
--- more_headers
X-Hidden-One: i am hidden
X-Hidden-Two: me 2
--- response_body
X-Hidden-One: i am hidden
X-Hidden-Two: me 2
