# vim:set ft= ts=4 sw=4 et:

use Test::Nginx::Socket::Lua;
use Cwd qw(cwd);

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

my $pwd = cwd();

our $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;$pwd/t/lib/?.lua;;";
    lua_package_cpath "/usr/local/openresty-debug/lualib/?.so;/usr/local/openresty/lualib/?.so;;";
};

$ENV{TEST_NGINX_RESOLVER} = '8.8.8.8';

no_long_string();
#no_diff();

run_tests();

__DATA__

=== TEST 1: basic
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form = upload:new(5)

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data; boundary=---------------------------820127721219505131303151179
--- request eval
qq{POST /t\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="file1"; filename="a.txt"\r
Content-Type: text/plain\r
\r
Hello, world\r\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="test"\r
\r
value\r
\r\n-----------------------------820127721219505131303151179--\r
}
--- response_body
read: ["header",["Content-Disposition","form-data; name=\"file1\"; filename=\"a.txt\"","Content-Disposition: form-data; name=\"file1\"; filename=\"a.txt\""]]
read: ["header",["Content-Type","text/plain","Content-Type: text/plain"]]
read: ["body","Hello"]
read: ["body",", wor"]
read: ["body","ld"]
read: ["part_end"]
read: ["header",["Content-Disposition","form-data; name=\"test\"","Content-Disposition: form-data; name=\"test\""]]
read: ["body","value"]
read: ["body","\r\n"]
read: ["part_end"]
read: ["eof"]
read: ["eof"]
--- no_error_log
[error]



=== TEST 2: in-part header line too long
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form = upload:new(5)

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data; boundary=---------------------------820127721219505131303151179
--- request eval
qq{POST /t\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="file1"; filename="a.txt"\r
Content-Type: text/plain\r
} . ("Hello, world" x 64) . qq{\r\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="test"\r
\r
value\r
\r\n-----------------------------820127721219505131303151179--\r
}
--- response_body
read: ["header",["Content-Disposition","form-data; name=\"file1\"; filename=\"a.txt\"","Content-Disposition: form-data; name=\"file1\"; filename=\"a.txt\""]]
read: ["header",["Content-Type","text/plain","Content-Type: text/plain"]]
failed to read: line too long: Hello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, wo...
--- no_error_log
[error]



=== TEST 3: terminate line too long
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form = upload:new(5)

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data; boundary=---------------------------820127721219505131303151179
--- request eval
qq{POST /t\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="file1"; filename="a.txt"\r
Content-Type: text/plain\r
\r
Hello, world\r\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="test"\r
\r
value\r
\r\n-----------------------------820127721219505131303151179} . ("a" x 1024) . qq{--\r
}
--- response_body
read: ["header",["Content-Disposition","form-data; name=\"file1\"; filename=\"a.txt\"","Content-Disposition: form-data; name=\"file1\"; filename=\"a.txt\""]]
read: ["header",["Content-Type","text/plain","Content-Type: text/plain"]]
read: ["body","Hello"]
read: ["body",", wor"]
read: ["body","ld"]
read: ["part_end"]
read: ["header",["Content-Disposition","form-data; name=\"test\"","Content-Disposition: form-data; name=\"test\""]]
read: ["body","value"]
read: ["body","\r\n"]
failed to read: line too long: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa...
--- no_error_log
[error]



=== TEST 4: example from RFC 1521
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form = upload:new(20)

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
content-TYPE: multipart/form-data; boundary="simple boundary"
--- request eval
qq{POST /t
This is the preamble.  It is to be ignored, though it
is a handy place for mail composers to include an
explanatory note to non-MIME conformant readers.
--simple boundary\r
\r
This is implicitly typed plain ASCII text.
It does NOT end with a linebreak.\r
--simple boundary\r
Content-type: text/plain; charset=us-ascii\r
\r
This is explicitly typed plain ASCII text.
It DOES end with a linebreak.
\r
--simple boundary--\r
This is the epilogue.  It is also to be ignored.

}
--- response_body
read: ["body","This is implicitly t"]
read: ["body","yped plain ASCII tex"]
read: ["body","t.\nIt does NOT end w"]
read: ["body","ith a linebreak."]
read: ["part_end"]
read: ["header",["Content-type","text/plain; charset=us-ascii","Content-type: text/plain; charset=us-ascii"]]
read: ["body","This is explicitly t"]
read: ["body","yped plain ASCII tex"]
read: ["body","t.\nIt DOES end with "]
read: ["body","a linebreak.\n"]
read: ["part_end"]
read: ["eof"]
read: ["eof"]
--- no_error_log
[error]



=== TEST 5: example from RFC 1521, no double quotes for the boundary value in the Content-Type response header
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form = upload:new(20)

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data; boundary=simple boundary
--- request eval
qq{POST /t
This is the preamble.  It is to be ignored, though it
is a handy place for mail composers to include an
explanatory note to non-MIME conformant readers.
--simple boundary\r
\r
This is implicitly typed plain ASCII text.
It does NOT end with a linebreak.\r
--simple boundary\r
Content-type: text/plain; charset=us-ascii\r
\r
This is explicitly typed plain ASCII text.
It DOES end with a linebreak.
\r
--simple boundary--\r
This is the epilogue.  It is also to be ignored.

}
--- response_body
read: ["body","This is implicitly t"]
read: ["body","yped plain ASCII tex"]
read: ["body","t.\nIt does NOT end w"]
read: ["body","ith a linebreak."]
read: ["part_end"]
read: ["header",["Content-type","text/plain; charset=us-ascii","Content-type: text/plain; charset=us-ascii"]]
read: ["body","This is explicitly t"]
read: ["body","yped plain ASCII tex"]
read: ["body","t.\nIt DOES end with "]
read: ["body","a linebreak.\n"]
read: ["part_end"]
read: ["eof"]
read: ["eof"]
--- no_error_log
[error]



=== TEST 6: example from RFC 1521, using the default chunk size
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form = upload:new()

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data; boundary=simple boundary
--- request eval
qq{POST /t
This is the preamble.  It is to be ignored, though it
is a handy place for mail composers to include an
explanatory note to non-MIME conformant readers.
--simple boundary\r
\r
This is implicitly typed plain ASCII text.
It does NOT end with a linebreak.\r
--simple boundary\r
Content-type: text/plain; charset=us-ascii\r
\r
This is explicitly typed plain ASCII text.
It DOES end with a linebreak.
\r
--simple boundary--\r
This is the epilogue.  It is also to be ignored.

}

--- response_body
read: ["body","This is implicitly typed plain ASCII text.\nIt does NOT end with a linebreak."]
read: ["part_end"]
read: ["header",["Content-type","text/plain; charset=us-ascii","Content-type: text/plain; charset=us-ascii"]]
read: ["body","This is explicitly typed plain ASCII text.\nIt DOES end with a linebreak.\n"]
read: ["part_end"]
read: ["eof"]
read: ["eof"]
--- no_error_log
[error]



=== TEST 7: github issue #2: cannot parse boundary - no space before parameter (w/o quotes)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form, err = upload:new(5)
            if not form then
                ngx.say("cannot get form: ", err)
                return
            end

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data;boundary=---------------------------820127721219505131303151179
--- request eval
qq{POST /t\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="file1"; filename="a.txt"\r
Content-Type: text/plain\r
\r
Hello, world\r\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="test"\r
\r
value\r
\r\n-----------------------------820127721219505131303151179--\r
}
--- response_body
read: ["header",["Content-Disposition","form-data; name=\"file1\"; filename=\"a.txt\"","Content-Disposition: form-data; name=\"file1\"; filename=\"a.txt\""]]
read: ["header",["Content-Type","text/plain","Content-Type: text/plain"]]
read: ["body","Hello"]
read: ["body",", wor"]
read: ["body","ld"]
read: ["part_end"]
read: ["header",["Content-Disposition","form-data; name=\"test\"","Content-Disposition: form-data; name=\"test\""]]
read: ["body","value"]
read: ["body","\r\n"]
read: ["part_end"]
read: ["eof"]
read: ["eof"]
--- no_error_log
[error]



=== TEST 8: github issue #2: cannot parse boundary - no space before parameter (with quotes)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form, err = upload:new(5)
            if not form then
                ngx.say("cannot get form: ", err)
                return
            end

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data;boundary="---------------------------820127721219505131303151179"
--- request eval
qq{POST /t\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="file1"; filename="a.txt"\r
Content-Type: text/plain\r
\r
Hello, world\r\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="test"\r
\r
value\r
\r\n-----------------------------820127721219505131303151179--\r
}
--- response_body
read: ["header",["Content-Disposition","form-data; name=\"file1\"; filename=\"a.txt\"","Content-Disposition: form-data; name=\"file1\"; filename=\"a.txt\""]]
read: ["header",["Content-Type","text/plain","Content-Type: text/plain"]]
read: ["body","Hello"]
read: ["body",", wor"]
read: ["body","ld"]
read: ["part_end"]
read: ["header",["Content-Disposition","form-data; name=\"test\"","Content-Disposition: form-data; name=\"test\""]]
read: ["body","value"]
read: ["body","\r\n"]
read: ["part_end"]
read: ["eof"]
read: ["eof"]
--- no_error_log
[error]



=== TEST 9: multiple Content-Type headers
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form = upload:new(5)

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data; boundary=---------------------------820127721219505131303151179
Content-Type: multipart/form-data; boundary=---------------------------820127721219505131303151179

--- request eval
qq{POST /t\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="file1"; filename="a.txt"\r
Content-Type: text/plain\r
\r
Hello, world\r\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="test"\r
\r
value\r
\r\n-----------------------------820127721219505131303151179--\r
}
--- response_body
read: ["header",["Content-Disposition","form-data; name=\"file1\"; filename=\"a.txt\"","Content-Disposition: form-data; name=\"file1\"; filename=\"a.txt\""]]
read: ["header",["Content-Type","text/plain","Content-Type: text/plain"]]
read: ["body","Hello"]
read: ["body",", wor"]
read: ["body","ld"]
read: ["part_end"]
read: ["header",["Content-Disposition","form-data; name=\"test\"","Content-Disposition: form-data; name=\"test\""]]
read: ["body","value"]
read: ["body","\r\n"]
read: ["part_end"]
read: ["eof"]
read: ["eof"]
--- no_error_log
[error]



=== TEST 10: long in-part header line
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local upload = require "resty.upload"
            local ljson = require "ljson"

            local form = upload:new(5, 1024) -- max_line_size = 1024

            form:set_timeout(1000) -- 1 sec

            while true do
                local typ, res, err = form:read()
                if not typ then
                    ngx.say("failed to read: ", err)
                    return
                end

                ngx.say("read: ", ljson.encode({typ, res}))

                if typ == "eof" then
                    break
                end
            end

            local typ, res, err = form:read()
            ngx.say("read: ", ljson.encode({typ, res}))
        ';
    }
--- more_headers
Content-Type: multipart/form-data; boundary=---------------------------820127721219505131303151179
--- request eval
qq{POST /t\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="file1"; filename="a.txt"\r
Content-Type: text/plain\r
} . ("Hello, world" x 64) . qq{\r\n-----------------------------820127721219505131303151179\r
Content-Disposition: form-data; name="test"\r
\r
value\r
\r\n-----------------------------820127721219505131303151179--\r
}
--- response_body
read: ["header",["Content-Disposition","form-data; name=\"file1\"; filename=\"a.txt\"","Content-Disposition: form-data; name=\"file1\"; filename=\"a.txt\""]]
read: ["header",["Content-Type","text/plain","Content-Type: text/plain"]]
read: ["header","Hello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, worldHello, world"]
read: ["header","-----------------------------820127721219505131303151179"]
read: ["header",["Content-Disposition","form-data; name=\"test\"","Content-Disposition: form-data; name=\"test\""]]
read: ["body","value"]
read: ["body","\r\n"]
read: ["part_end"]
read: ["eof"]
read: ["eof"]
--- no_error_log
[error]

