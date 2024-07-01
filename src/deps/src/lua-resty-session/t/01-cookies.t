use Test::Nginx::Socket;
repeat_each(2);

$ENV{TEST_NGINX_NXSOCK} ||= html_dir();
plan tests => repeat_each() * blocks() * 3 + 4;

run_tests();

__DATA__

=== TEST 1: session cookie is returned
--- http_config
  init_by_lua_block {
    require("resty.session").init({
      storage  = "cookie",
    })
  }
--- config
location = /test {
    content_by_lua_block {
      local session = require "resty.session".new()
      local ok = session:save()
      if ok then
        ngx.say("yay")
      end
    }
}

--- request
GET /test
--- response_body
yay
--- response_headers_like
Set-Cookie: .*session=.+;.*
--- error_code: 200
--- no_error_log
[error]


=== TEST 2: remember cookie is returned when remember=true
--- http_config
  init_by_lua_block {
    require("resty.session").init({
      remember = true,
      storage  = "cookie",
    })
  }
--- config
location = /test {
    content_by_lua_block {
      local session = require "resty.session".new()
      local ok = session:save()
     
      if ok then
        ngx.say("yay")
      end
    }
}

--- request
GET /test
--- response_body
yay
--- response_headers_like
Set-Cookie: .*remember=.+;.*
--- error_code: 200
--- no_error_log
[error]


=== TEST 3: session.open() opens a session from a valid cookie and data is
extracted correctly
--- http_config
  init_by_lua_block {
    require("resty.session").init({
      secret           = "RaJKp8UQW1",
      storage          = "cookie",
      audience         = "my_application",
      idling_timeout   = 0,
      rolling_timeout  = 0,
      absolute_timeout = 0,
    })
  }
--- config
location = /test {
    content_by_lua_block {
      local session = require "resty.session".open()
      local sub     = session:get_subject()
      local aud     = session:get_audience()
      local quote   = session:get("quote")
     
      ngx.say(sub .. "|" .. aud .. "|" .. quote)
    }
}

--- request
GET /test
--- more_headers
Cookie: session=AQAAS3ZGU0k8tUKsWSci9Fb6PM5xbm469FlR5g_B5HWZ6KYGSOZjAAAAAABcAABTCuHjqpE7B6Ux7m4GCylZAAAAzcWnTvzG51whooR_4QQwDgGdMOOa5W7tG4JWiDFU3zuYLFzakWEi-y-ogrwTpnt24zQXP_uJK7r5lMPNzRSMJM9H1a_MIegzEMm-QSgVRaoZVJq3Oo; Path=/; SameSite=Lax; HttpOnly
--- response_body
Lua Fan|my_application|Lorem ipsum dolor sit amet
--- error_code: 200
--- no_error_log
[error]


=== TEST 4: clear_request_cookie() clears session Cookie from request to
upstream
--- http_config
  init_by_lua_block {
    require("resty.session").init({
      secret           = "RaJKp8UQW1",
      storage          = "cookie",
      audience         = "my_application",
      idling_timeout   = 0,
      rolling_timeout  = 0,
      absolute_timeout = 0,
    })
  }

  server {
    listen unix:/$TEST_NGINX_NXSOCK/nginx.sock;

    location /t {
        content_by_lua_block {
          local headers = ngx.req.get_headers()
          ngx.say("session_cookie: [", tostring(headers["Cookie"]), "]")
        }
    }
  }

--- config
location = /test {
    access_by_lua_block {
      local session = require "resty.session".open()
      session:clear_request_cookie()
    }
    proxy_pass http://unix:/$TEST_NGINX_NXSOCK/nginx.sock;
}

--- request
GET /test
--- more_headers
Cookie: session=AQAAS3ZGU0k8tUKsWSci9Fb6PM5xbm469FlR5g_B5HWZ6KYGSOZjAAAAAABcAABTCuHjqpE7B6Ux7m4GCylZAAAAzcWnTvzG51whooR_4QQwDgGdMOOa5W7tG4JWiDFU3zuYLFzakWEi-y-ogrwTpnt24zQXP_uJK7r5lMPNzRSMJM9H1a_MIegzEMm-QSgVRaoZVJq3Oo; Path=/; SameSite=Lax; HttpOnly
--- response_body
session_cookie: [Path=/; SameSite=Lax; HttpOnly]
--- error_code: 200
--- no_error_log
[error]
