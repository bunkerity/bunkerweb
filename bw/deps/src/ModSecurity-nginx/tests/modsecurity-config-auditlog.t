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
                SecRule ARGS "@streq root" "id:21,phase:1,auditlog,status:302,redirect:http://www.modsecurity.org"
                SecDebugLog %%TESTDIR%%/auditlog-debug-root.txt
                SecDebugLogLevel 9
                SecAuditEngine RelevantOnly
                SecAuditLogParts AB
                SecAuditLog %%TESTDIR%%/auditlog-root.txt
                SecAuditLogType Serial
                SecAuditLogStorageDir %%TESTDIR%%/
            ';
        }

        location /subfolder1/subfolder2 {
            modsecurity_rules '
                SecRule ARGS "@streq subfolder2" "id:41,phase:1,status:302,auditlog,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq subfolder1" "id:42,phase:1,status:302,auditlog,redirect:http://www.modsecurity.org"
                SecDebugLog %%TESTDIR%%/auditlog-debug-subfolder2.txt
                SecDebugLogLevel 9
                SecAuditEngine RelevantOnly
                SecAuditLogParts AB
                SecResponseBodyAccess On
                SecAuditLog %%TESTDIR%%/auditlog-subfolder2.txt
                SecAuditLogType Serial
                SecAuditLogStorageDir %%TESTDIR%%/
            ';
        }

        location /subfolder1 {
            modsecurity_rules '
                SecRule ARGS "@streq subfolder1" "id:31,phase:1,status:302,auditlog,redirect:http://www.modsecurity.org"
                SecDebugLog %%TESTDIR%%/auditlog-debug-subfolder1.txt
                SecDebugLogLevel 9
                SecAuditLogParts AB
                SecAuditEngine RelevantOnly
                SecAuditLog %%TESTDIR%%/auditlog-subfolder1.txt
                SecAuditLogType Serial
                SecAuditLogStorageDir %%TESTDIR%%/
            ';
        }

        location /subfolder3/subfolder4 {
            modsecurity_rules '
                SecResponseBodyAccess On
                SecRule ARGS "@streq subfolder4" "id:61,phase:1,status:302,auditlog,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq subfolder3" "id:62,phase:1,status:302,auditlog,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq subfolder4withE" "id:63,phase:1,ctl:auditLogParts=+E,auditlog"
                SecDebugLog %%TESTDIR%%/auditlog-debug-subfolder4.txt
                SecDebugLogLevel 9
                SecAuditEngine RelevantOnly
                SecAuditLogParts AB
                SecAuditLog %%TESTDIR%%/auditlog-subfolder4.txt
                SecAuditLogType Serial
                SecAuditLogStorageDir %%TESTDIR%%/
            ';
        }

        location /subfolder3 {
            modsecurity_rules '
                SecRule ARGS "@streq subfolder3" "id:51,phase:1,status:302,auditlog,redirect:http://www.modsecurity.org"
                SecDebugLog %%TESTDIR%%/auditlog-debug-subfolder3.txt
                SecDebugLogLevel 9
                SecAuditLogParts AB
                SecAuditEngine RelevantOnly
                SecAuditLog %%TESTDIR%%/auditlog-subfolder3.txt
                SecAuditLogType Serial
                SecAuditLogStorageDir %%TESTDIR%%/
            ';
        }

    }
}
EOF

$t->write_file("/index.html", "should be moved/blocked before this.");
mkdir($t->testdir() . '/subfolder1');
$t->write_file("/subfolder1/index.html", "should be moved/blocked before this.");
mkdir($t->testdir() . '/subfolder1/subfolder2');
$t->write_file("/subfolder1/subfolder2/index.html", "should be moved/blocked before this.");
mkdir($t->testdir() . '/subfolder3');
$t->write_file("/subfolder3/index.html", "should be moved/blocked before this.");
mkdir($t->testdir() . '/subfolder3/subfolder4');
$t->write_file("/subfolder3/subfolder4/index.html", "should be moved/blocked before this.");

$t->run();
$t->plan(9);

###############################################################################

my $d = $t->testdir();

my $r;
# Performing requests at root
$r = http_get('/index.html?what=root');
$r = http_get('/index.html?what=subfolder1');
$r = http_get('/index.html?what=subfolder2');
$r = http_get('/index.html?what=subfolder3');
$r = http_get('/index.html?what=subfolder4');

# Performing requests at subfolder1
$r = http_get('/subfolder1/index.html?what=root');
$r = http_get('/subfolder1/index.html?what=subfolder1');
$r = http_get('/subfolder1/index.html?what=subfolder2');
$r = http_get('/subfolder1/index.html?what=subfolder3');
$r = http_get('/subfolder1/index.html?what=subfolder4');

# Performing requests at subfolder2
$r = http_get('/subfolder1/subfolder2/index.html?what=root');
$r = http_get('/subfolder1/subfolder2/index.html?what=subfolder1');
$r = http_get('/subfolder1/subfolder2/index.html?what=subfolder2');
$r = http_get('/subfolder1/subfolder2/index.html?what=subfolder3');
$r = http_get('/subfolder1/subfolder2/index.html?what=subfolder4');

# Performing requests at subfolder3
$r = http_get('/subfolder3/index.html?what=root');
$r = http_get('/subfolder3/index.html?what=subfolder1');
$r = http_get('/subfolder3/index.html?what=subfolder2');
$r = http_get('/subfolder3/index.html?what=subfolder3');
$r = http_get('/subfolder3/index.html?what=subfolder4');

# Performing requests at subfolder4
$r = http_get('/subfolder3/subfolder4/index.html?what=root');
$r = http_get('/subfolder3/subfolder4/index.html?what=subfolder1');
$r = http_get('/subfolder3/subfolder4/index.html?what=subfolder2');
$r = http_get('/subfolder3/subfolder4/index.html?what=subfolder3');
$r = http_get('/subfolder3/subfolder4/index.html?what=subfolder4');
$r = http_get('/subfolder3/subfolder4/index.html?what=subfolder4withE');

my $root = do {
    local $/ = undef;
    open my $fh, "<", "$d/auditlog-root.txt"
        or die "could not open: $!";
    <$fh>;
};
my $subfolder1 = do {
    local $/ = undef;
    open my $fh, "<", "$d/auditlog-subfolder1.txt"
        or die "could not open: $!";
    <$fh>;
};
my $subfolder2 = do {
    local $/ = undef;
    open my $fh, "<", "$d/auditlog-subfolder2.txt"
        or die "could not open: $!";
    <$fh>;
};
my $subfolder3 = do {
    local $/ = undef;
    open my $fh, "<", "$d/auditlog-subfolder3.txt"
        or die "could not open: $!";
    <$fh>;
};
my $subfolder4 = do {
    local $/ = undef;
    open my $fh, "<", "$d/auditlog-subfolder4.txt"
        or die "could not open: $!";
    <$fh>;
};


like($root, qr/what=root/, 'root');
like($subfolder1, qr/what=subfolder1/, 'subfolder1');
like($subfolder2, qr/what=subfolder2/, 'subfolder2');
like($subfolder2, qr/what=subfolder1/, 'subfolder2 / subfolder1');

like($subfolder3, qr/what=subfolder3/, 'subfolder3');
like($subfolder4, qr/what=subfolder4/, 'subfolder4');
like($subfolder4, qr/what=subfolder3/, 'subfolder4 / subfolder3');

like($subfolder4, qr/what=subfolder4withE/, 'subfolder4');
like($subfolder4, qr/---E--/, 'subfolder4');
