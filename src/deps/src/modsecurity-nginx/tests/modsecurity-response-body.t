#!/usr/bin/perl

# (C) Andrei Belov

# Tests for ModSecurity-nginx connector (response body operations).

###############################################################################

use warnings;
use strict;

use Test::More;

BEGIN { use FindBin; chdir($FindBin::Bin); }

use lib 'lib';
use Test::Nginx;

###############################################################################

select STDERR; $| = 1;
select STDOUT; $| = 1;

my $t = Test::Nginx->new()->has(qw/http/);

$t->write_file_expand('nginx.conf', <<'EOF');

%%TEST_GLOBALS%%

daemon off;

events {
}

http {
    %%TEST_GLOBALS_HTTP%%

    server {
        listen       127.0.0.1:8080;
        server_name  localhost;

        modsecurity on;

        location /body1 {
            default_type text/plain;
            modsecurity_rules '
                SecRuleEngine On
                SecResponseBodyAccess On
                SecResponseBodyLimit 128
                SecRule RESPONSE_BODY "@rx BAD BODY" "id:11,phase:response,deny,log,status:403"
            ';
        }
    }
}
EOF

$t->write_file("/body1", "BAD BODY");
$t->run();
$t->todo_alerts();
$t->plan(1);

###############################################################################

TODO: {
local $TODO = 'not yet';

like(http_get('/body1'), qr/^HTTP.*403/, 'response body (block)');
}

