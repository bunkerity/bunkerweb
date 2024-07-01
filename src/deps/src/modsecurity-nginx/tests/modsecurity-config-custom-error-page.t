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
        server_name  s1;

        error_page 403 /403.html;

        location /403.html {
            root %%TESTDIR%%/http;
            internal;
        }

        location / {
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecRule ARGS "@streq root" "id:10,phase:1,auditlog,status:403,deny"
                SecDebugLog %%TESTDIR%%/auditlog-debug-local.txt
                SecDebugLogLevel 9
                SecAuditEngine RelevantOnly
                SecAuditLogParts ABIJDEFHZ
                SecAuditLog %%TESTDIR%%/auditlog-local.txt
                SecAuditLogType Serial
                SecAuditLogStorageDir %%TESTDIR%%/
            ';
        }
    }

    server {
        listen       127.0.0.1:8080;
        server_name  s2;

        modsecurity on;
        modsecurity_rules '
            SecRuleEngine On
            SecRule ARGS "@streq root" "id:10,phase:1,auditlog,status:403,deny"
            SecDebugLog %%TESTDIR%%/auditlog-debug-global.txt
            SecDebugLogLevel 9
            SecAuditEngine RelevantOnly
            SecAuditLogParts ABIJDEFHZ
            SecAuditLog %%TESTDIR%%/auditlog-global.txt
            SecAuditLogType Serial
            SecAuditLogStorageDir %%TESTDIR%%/
        ';

        error_page 403 /403.html;

        location /403.html {
            modsecurity off;
            root %%TESTDIR%%/http;
            internal;
        }

        location / {
        }
    }
}
EOF

my $index_txt = "This is the index page.";
my $custom_txt = "This is a custom error page.";

$t->write_file("/index.html", $index_txt);
mkdir($t->testdir() . '/http');
$t->write_file("/http/403.html", $custom_txt);

$t->run();
$t->plan(10);

###############################################################################

my $d = $t->testdir();

my $t1;
my $t2;
my $t3;
my $t4;

# Performing requests to a server with ModSecurity enabled at location context
$t1 = http_get_host('s1', '/index.html?what=root');
$t2 = http_get_host('s1', '/index.html?what=other');

# Performing requests to a server with ModSecurity enabled at server context
$t3 = http_get_host('s2', '/index.html?what=root');
$t4 = http_get_host('s2', '/index.html?what=other');

my $local = do {
    local $/ = undef;
    open my $fh, "<", "$d/auditlog-local.txt"
        or die "could not open: $!";
    <$fh>;
};

my $global = do {
    local $/ = undef;
    open my $fh, "<", "$d/auditlog-global.txt"
        or die "could not open: $!";
    <$fh>;
};

like($t1, qr/$custom_txt/, 'ModSecurity at location / root');
like($t2, qr/$index_txt/, 'ModSecurity at location / other');
like($local, qr/what=root/, 'ModSecurity at location / root present in auditlog');
unlike($local, qr/what=other/, 'ModSecurity at location / other not present in auditlog');

like($t3, qr/$custom_txt/, 'ModSecurity at server / root');
like($t4, qr/$index_txt/, 'ModSecurity at server / other');
like($global, qr/what=root/, 'ModSecurity at server / root present in auditlog');
unlike($global, qr/what=other/, 'ModSecurity at server / other not present in auditlog');

like($local, qr/Access denied with code 403/, 'ModSecurity at location / 403 in auditlog');
like($global, qr/Access denied with code 403/, 'ModSecurity at server / 403 in auditlog');

###############################################################################

sub http_get_host {
	my ($host, $url) = @_;
	return http(<<EOF);
GET $url HTTP/1.0
Host: $host

EOF
}

###############################################################################
