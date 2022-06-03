#!/usr/bin/perl

# (C) Andrei Belov

# Tests for ModSecurity-nginx connector (scoring).

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

        location /absolute {
            modsecurity_rules '
                SecRuleEngine On
                SecRule ARGS "@streq badarg1" "id:11,phase:2,setvar:tx.score=1"
                SecRule ARGS "@streq badarg2" "id:12,phase:2,setvar:tx.score=2"
                SecRule TX:SCORE "@ge 2" "id:199,phase:request,deny,log,status:403"
            ';
        }

        location /iterative {
            modsecurity_rules '
                SecRuleEngine On
                SecRule ARGS "@streq badarg1" "id:21,phase:2,setvar:tx.score=+1"
                SecRule ARGS "@streq badarg2" "id:22,phase:2,setvar:tx.score=+1"
                SecRule ARGS "@streq badarg3" "id:23,phase:2,setvar:tx.score=+1"
                SecRule TX:SCORE "@ge 3" "id:299,phase:request,deny,log,status:403"
            ';
        }
    }
}
EOF

$t->write_file("/absolute", "should be moved/blocked before this.");
$t->write_file("/iterative", "should be moved/blocked before this.");
$t->run();
$t->plan(5);

###############################################################################

like(http_get('/absolute?what=badarg1'), qr/should be moved\/blocked before this./, 'absolute scoring 1 (pass)');
like(http_get('/absolute?what=badarg2'), qr/^HTTP.*403/, 'absolute scoring 2 (block)');

like(http_get('/iterative?arg1=badarg1'), qr/should be moved\/blocked before this./, 'iterative scoring 1 (pass)');
like(http_get('/iterative?arg1=badarg1&arg2=badarg2'), qr/should be moved\/blocked before this./, 'iterative scoring 2 (pass)');
like(http_get('/iterative?arg1=badarg1&arg2=badarg2&arg3=badarg3'), qr/^HTTP.*403/, 'iterative scoring 3 (block)');

