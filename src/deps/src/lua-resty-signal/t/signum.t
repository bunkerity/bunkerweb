# vi:ft=

use lib '.';
use t::TestKiller;

plan tests => 3 * blocks();

no_long_string();
#no_diff();

run_tests();

__DATA__

=== TEST 1: signals whose values are specified by POSIX
--- config
    location = /t {
        content_by_lua_block {
            local resty_signal = require "resty.signal"
            local ffi = require "ffi"
            local say = ngx.say
            local signum = resty_signal.signum

            for i, signame in ipairs{ "ABRT", "ALRM", "HUP", "INT", "KILL",
                                      "QUIT", "TERM", "TRAP", "BLAH" } do
                say(signame, ": ", tostring(signum(signame)))
            end

            local linux_signals = {
                NONE = 0,
                HUP = 1,
                INT = 2,
                QUIT = 3,
                ILL = 4,
                TRAP = 5,
                ABRT = 6,
                BUS = 7,
                FPE = 8,
                KILL = 9,
                USR1 = 10,
                SEGV = 11,
                USR2 = 12,
                PIPE = 13,
                ALRM = 14,
                TERM = 15,
                CHLD = 17,
                CONT = 18,
                STOP = 19,
                TSTP = 20,
                TTIN = 21,
                TTOU = 22,
                URG = 23,
                XCPU = 24,
                XFSZ = 25,
                VTALRM = 26,
                PROF = 27,
                WINCH = 28,
                IO = 29,
                PWR = 30
            }

            local macosx_signals = {
                HUP = 1,
                INT = 2,
                QUIT = 3,
                ILL = 4,
                TRAP = 5,
                ABRT = 6,
                EMT = 7,
                FPE = 8,
                KILL = 9,
                BUS = 10,
                SEGV = 11,
                SYS = 12,
                PIPE = 13,
                ALRM = 14,
                TERM = 15,
                URG = 16,
                STOP = 17,
                TSTP = 18,
                CONT = 19,
                CHLD = 20,
                TTIN = 21,
                TTOU = 22,
                IO = 23,
                XCPU = 24,
                XFSZ = 25,
                VTALRM = 26,
                PROF = 27,
                WINCH = 28,
                INFO = 29,
                USR1 = 30,
                USR2 = 31
            }

            if ffi.os == "Linux" then
                for signame, num in pairs(linux_signals) do
                    assert(num == tonumber(signum(signame)))
                end
            elseif ffi.os == "OSX" then
                for signame, num in pairs(macosx_signals) do
                    assert(num == tonumber(signum(signame)))
                end
            end
        }
    }
--- response_body
ABRT: 6
ALRM: 14
HUP: 1
INT: 2
KILL: 9
QUIT: 3
TERM: 15
TRAP: 5
BLAH: nil
