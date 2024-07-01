#!/usr/bin/env perl

use strict;
use warnings;

my $ignore_value;
while (<>) {
    if (/use Test::Nginx::Socket::Lua([^:].*)/) {
        print "use Test::Nginx::Socket::Lua::Stream$1";
        next;
    }

    if ($ignore_value) {
        if (/^---/) {
            undef $ignore_value;
        } else {
            next;
        }
    }

    if (/^--- http_config\b(.*)/) {
        print "--- stream_config$1\n";
        next;
    }

    if (/^--- config\b(.*)/) {
        print "--- stream_server_config$1\n";
        next;
    }

    if (/^\s*location .*/) {
        next;
    }

    if (/^\s*(set|init|log|init_worker|content|rewrite|access)_by_lua (['"])(.*?)\2;/) {
        print "    ${1}_by_lua_block { $3 }\n";
        next;
    }

    if (/^\s*(set|init|log|init_worker|content|rewrite|access)_by_lua (['"])\s*$/) {
        print "    ${1}_by_lua_block {\n";
        next;
    }

    if (/^--- ignore_response$/) {
        print "--- stream_response\n";
        next;
    }

    if (/^--- error_code/) {
        next;
    }

    if (/^--- request[^:]*$/) {
        $ignore_value = 1;
        next;
    }

    if (/^\s*["'];$/) {
        next;
    }

    if (/^--- response_body\b(.*)/) {
        print "--- stream_response$1\n";
        next;
    }

    if (/^--- response_body_like\b(.*)/) {
        print "--- stream_response_like$1\n";
        next;
    }

    print;
}
