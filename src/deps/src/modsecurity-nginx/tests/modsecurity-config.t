#!/usr/bin/perl

#
# ModSecurity, http://www.modsecurity.org/
# Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
#
# You may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# If any of the files related to licensing are missing or if you have any
# other questions related to licensing please contact Trustwave Holdings, Inc.
# directly using the email address security@modsecurity.org.
#


# Tests for ModSecurity module.

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
        modsecurity_rules '
            SecRuleEngine On
            SecRule ARGS "@streq whee" "id:10,phase:2"
            SecRule ARGS "@streq whee" "id:11,phase:2"
        ';

        location / {
            modsecurity_rules '
                SecRuleEngine On
                SecRule ARGS "@streq root" "id:21,phase:1,status:302,redirect:http://www.modsecurity.org"
            ';
        }

        location /subfolder1 {
            modsecurity_rules '
                SecRuleEngine On
                SecRule ARGS "@streq subfolder1" "id:31,phase:1,status:302,redirect:http://www.modsecurity.org"
            ';
            location /subfolder1/subfolder2 {
                modsecurity_rules '
                    SecRuleEngine On
                    SecRule ARGS "@streq subfolder2" "id:41,phase:1,status:302,redirect:http://www.modsecurity.org"
                ';
            }
        }
    }
}
EOF

$t->write_file("/index.html", "should be moved/blocked before this.");
mkdir($t->testdir() . '/subfolder1');
$t->write_file("/subfolder1/index.html", "should be moved/blocked before this.");
mkdir($t->testdir() . '/subfolder1/subfolder2');
$t->write_file("/subfolder1/subfolder2/index.html", "should be moved/blocked before this.");

$t->run();
$t->plan(9);

###############################################################################


# Performing requests at root
like(http_get('/index.html?what=root'), qr/^HTTP.*302/, 'redirect 302 - root');
like(http_get('/index.html?what=subfolder1'), qr/should be moved\/blocked before this./, 'nothing - requested subfolder1 at root');
like(http_get('/index.html?what=subfolder2'), qr/should be moved\/blocked before this./, 'nothing - requested subfolder2 at root');

# Performing requests at subfolder1
like(http_get('/subfolder1/index.html?what=root'), qr/should be moved\/blocked before this./, 'nothing - requested root at subfolder 1');
like(http_get('/subfolder1/index.html?what=subfolder1'), qr/^HTTP.*302/, 'redirect 302 - subfolder 1');
like(http_get('/subfolder1/index.html?what=subfolder2'), qr/should be moved\/blocked before this./, 'nothing - requested subfolder2 at subfolder1');

# Performing requests at subfolder2
like(http_get('/subfolder1/subfolder2/index.html?what=root'), qr/should be moved\/blocked before this./, 'nothing - requested root at subfolder 2');
like(http_get('/subfolder1/subfolder2/index.html?what=subfolder1'), qr/^HTTP.*302/, 'redirect 302 - subfolder 2');
like(http_get('/subfolder1/subfolder2/index.html?what=subfolder2'), qr/^HTTP.*302/, 'redirect 302 - subfolder 2');


