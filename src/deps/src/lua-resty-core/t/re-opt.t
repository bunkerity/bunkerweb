# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * blocks() * 3;

no_diff();
no_long_string();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: default jit_stack_size too small
--- config
    location /re {
        content_by_lua_block {
            -- regex is taken from https://github.com/JuliaLang/julia/issues/8278
            local very_long_string = [[71.163.72.113 - - [30/Jul/2014:16:40:55 -0700] "GET emptymind.org/thevacantwall/wp-content/uploads/2013/02/DSC_006421.jpg HTTP/1.1" 200 492513 "http://images.search.yahoo.com/images/view;_ylt=AwrB8py9gdlTGEwADcSjzbkF;_ylu=X3oDMTI2cGZrZTA5BHNlYwNmcC1leHAEc2xrA2V4cARvaWQDNTA3NTRiMzYzY2E5OTEwNjBiMjc2YWJhMjkxMTEzY2MEZ3BvcwM0BGl0A2Jpbmc-?back=http%3A%2F%2Fus.yhs4.search.yahoo.com%2Fyhs%2Fsearch%3Fei%3DUTF-8%26p%3Dapartheid%2Bwall%2Bin%2Bpalestine%26type%3Dgrvydef%26param1%3D1%26param2%3Dsid%253Db01676f9c26355f014f8a9db87545d61%2526b%253DChrome%2526ip%253D71.163.72.113%2526p%253Dgroovorio%2526x%253DAC811262A746D3CD%2526dt%253DS940%2526f%253D7%2526a%253Dgrv_tuto1_14_30%26hsimp%3Dyhs-fullyhosted_003%26hspart%3Dironsource&w=588&h=387&imgurl=occupiedpalestine.files.wordpress.com%2F2012%2F08%2F5-peeking-through-the-wall.jpg%3Fw%3D588%26h%3D387&rurl=http%3A%2F%2Fwww.stopdebezetting.com%2Fwereldpers%2Fcompare-the-berlin-wall-vs-israel-s-apartheid-wall-in-palestine.html&size=49.0KB&name=...+%3Cb%3EApartheid+wall+in+Palestine%3C%2Fb%3E...+%7C+Or+you+go+peeking+through+the+%3Cb%3Ewall%3C%2Fb%3E&p=apartheid+wall+in+palestine&oid=50754b363ca991060b276aba291113cc&fr2=&fr=&tt=...+%3Cb%3EApartheid+wall+in+Palestine%3C%2Fb%3E...+%7C+Or+you+go+peeking+through+the+%3Cb%3Ewall%3C%2Fb%3E&b=0&ni=21&no=4&ts=&tab=organic&sigr=13evdtqdq&sigb=19k7nsjvb&sigi=12o2la1db&sigt=12lia2m0j&sign=12lia2m0j&.crumb=.yUtKgFI6DE&hsimp=yhs-fullyhosted_003&hspart=ironsource" "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36]]
            local very_complicated_regex = [[([\d\.]+) ([\w.-]+) ([\w.-]+) (\[.+\]) "([^"\r\n]*|[^"\r\n\[]*\[.+\][^"]+|[^"\r\n]+.[^"]+)" (\d{3}) (\d+|-) ("(?:[^"]|\")+)"? ("(?:[^"]|\")+)"?]]
            local from, to, err = ngx.re.find(very_long_string, very_complicated_regex, "jo")
            if from or to then
                ngx.say("from: ", from)
                ngx.say("to: ", to)
            else
                if err then
                    ngx.say("error: ", err)
                    return
                end
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body
error: pcre_exec() failed: -27
--- no_error_log
[error]
--- timeout: 10



=== TEST 2: increase jit_stack_size
--- http_config eval
qq{
    lua_package_path '$t::TestCore::lua_package_path';
    init_by_lua_block {
        $t::TestCore::init_by_lua_block

        local ngx_re = require "ngx.re"
        ngx_re.opt("jit_stack_size", 128 * 1024)
    }
}
--- config
    location /re {
        content_by_lua_block {
            -- regex is taken from https://github.com/JuliaLang/julia/issues/8278
            local very_long_string = [[71.163.72.113 - - [30/Jul/2014:16:40:55 -0700] "GET emptymind.org/thevacantwall/wp-content/uploads/2013/02/DSC_006421.jpg HTTP/1.1" 200 492513 "http://images.search.yahoo.com/images/view;_ylt=AwrB8py9gdlTGEwADcSjzbkF;_ylu=X3oDMTI2cGZrZTA5BHNlYwNmcC1leHAEc2xrA2V4cARvaWQDNTA3NTRiMzYzY2E5OTEwNjBiMjc2YWJhMjkxMTEzY2MEZ3BvcwM0BGl0A2Jpbmc-?back=http%3A%2F%2Fus.yhs4.search.yahoo.com%2Fyhs%2Fsearch%3Fei%3DUTF-8%26p%3Dapartheid%2Bwall%2Bin%2Bpalestine%26type%3Dgrvydef%26param1%3D1%26param2%3Dsid%253Db01676f9c26355f014f8a9db87545d61%2526b%253DChrome%2526ip%253D71.163.72.113%2526p%253Dgroovorio%2526x%253DAC811262A746D3CD%2526dt%253DS940%2526f%253D7%2526a%253Dgrv_tuto1_14_30%26hsimp%3Dyhs-fullyhosted_003%26hspart%3Dironsource&w=588&h=387&imgurl=occupiedpalestine.files.wordpress.com%2F2012%2F08%2F5-peeking-through-the-wall.jpg%3Fw%3D588%26h%3D387&rurl=http%3A%2F%2Fwww.stopdebezetting.com%2Fwereldpers%2Fcompare-the-berlin-wall-vs-israel-s-apartheid-wall-in-palestine.html&size=49.0KB&name=...+%3Cb%3EApartheid+wall+in+Palestine%3C%2Fb%3E...+%7C+Or+you+go+peeking+through+the+%3Cb%3Ewall%3C%2Fb%3E&p=apartheid+wall+in+palestine&oid=50754b363ca991060b276aba291113cc&fr2=&fr=&tt=...+%3Cb%3EApartheid+wall+in+Palestine%3C%2Fb%3E...+%7C+Or+you+go+peeking+through+the+%3Cb%3Ewall%3C%2Fb%3E&b=0&ni=21&no=4&ts=&tab=organic&sigr=13evdtqdq&sigb=19k7nsjvb&sigi=12o2la1db&sigt=12lia2m0j&sign=12lia2m0j&.crumb=.yUtKgFI6DE&hsimp=yhs-fullyhosted_003&hspart=ironsource" "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36]]
            local very_complicated_regex = [[([\d\.]+) ([\w.-]+) ([\w.-]+) (\[.+\]) "([^"\r\n]*|[^"\r\n\[]*\[.+\][^"]+|[^"\r\n]+.[^"]+)" (\d{3}) (\d+|-) ("(?:[^"]|\")+)"? ("(?:[^"]|\")+)"?]]
            local from, to, err = ngx.re.find(very_long_string, very_complicated_regex, "jo")
            if from or to then
                ngx.say("from: ", from)
                ngx.say("to: ", to)
            else
                if err then
                    ngx.say("error: ", err)
                    return
                end
                ngx.say("not matched!")
            end
        }
    }
--- request
    GET /re
--- response_body
from: 1
to: 1563
--- no_error_log
[error]
--- timeout: 10



=== TEST 3: jit_stack_size change disallowed once regex cache is populated
--- config
    location /re {
        content_by_lua_block {
            local ngx_re = require "ngx.re"

            local status, err = pcall(ngx_re.opt, "jit_stack_size", 128 * 1024)
            if err then ngx.log(ngx.ERR, err) end
            local s = "hello, 1234"
            local from, to = ngx.re.find(s, "(hello world)|([0-9])", "jo")
            ngx.say("from: ", from)
            ngx.say("to: ", to)
        }
    }
--- request
    GET /re
--- response_body
from: 8
to: 8

--- grep_error_log eval
qr/changing jit stack size is not allowed when some regexs have already been compiled and cached/

--- grep_error_log_out eval
["", "changing jit stack size is not allowed when some regexs have already been compiled and cached\n"]
--- timeout: 10



=== TEST 4: passing unknown options to ngx_re.opt throws an error
--- config
    location /re {
        content_by_lua_block {
            local ngx_re = require "ngx.re"

            local status, err = pcall(ngx_re.opt, "foo", 123)
            ngx.say(err)
        }
    }
--- request
    GET /re
--- response_body_like chomp
unrecognized option name$
--- no_error_log
[error]
--- timeout: 10
