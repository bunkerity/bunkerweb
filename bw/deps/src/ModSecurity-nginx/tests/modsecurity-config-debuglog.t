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
                SecRule ARGS "@streq root" "id:21,phase:1,status:302,redirect:http://www.modsecurity.org"
                SecDebugLog %%TESTDIR%%/debuglog-root.txt
                SecDebugLogLevel 9
            ';
        }

        location /subfolder1 {
            modsecurity_rules '
                SecRule ARGS "@streq subfolder1" "id:31,phase:1,status:302,redirect:http://www.modsecurity.org"
                SecDebugLog %%TESTDIR%%/debuglog-subfolder1.txt
                SecDebugLogLevel 9
            ';
            location /subfolder1/subfolder2 {
                modsecurity_rules '
                    SecRule ARGS "@streq subfolder2" "id:41,phase:1,status:302,redirect:http://www.modsecurity.org"
                    SecDebugLog %%TESTDIR%%/debuglog-subfolder2.txt
                    SecDebugLogLevel 9
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
$t->plan(3);

###############################################################################

my $d = $t->testdir();

my $r;
# Performing requests at root
$r = http_get('/index.html?what=root');
$r = http_get('/index.html?what=subfolder1');
$r = http_get('/index.html?what=subfolder2');

# Performing requests at subfolder1
$r = http_get('/subfolder1/index.html?what=root');
$r = http_get('/subfolder1/index.html?what=subfolder1');
$r = http_get('/subfolder1/index.html?what=subfolder2');

# Performing requests at subfolder2
$r = http_get('/subfolder1/subfolder2/index.html?what=root');
$r = http_get('/subfolder1/subfolder2/index.html?what=subfolder1');
$r = http_get('/subfolder1/subfolder2/index.html?what=subfolder2');

my $root = do {
    local $/ = undef;
    open my $fh, "<", "$d/debuglog-root.txt"
        or die "could not open: $!";
    <$fh>;
};
my $subfolder1 = do {
    local $/ = undef;
    open my $fh, "<", "$d/debuglog-subfolder1.txt"
        or die "could not open: $!";
    <$fh>;
};
my $subfolder2 = do {
    local $/ = undef;
    open my $fh, "<", "$d/debuglog-subfolder2.txt"
        or die "could not open: $!";
    <$fh>;
};

like($root, qr/"what", value "root"/, 'root');
like($subfolder1, qr/"what", value "subfolder1"/, 'subfolder1');
like($subfolder2, qr/"what", value "subfolder2"/, 'subfolder2');



