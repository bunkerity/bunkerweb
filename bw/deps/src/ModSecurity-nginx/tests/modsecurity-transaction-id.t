#!/usr/bin/perl

# (C) Andrei Belov

# Tests for ModSecurity-nginx connector (modsecurity_transaction_id).

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

my $t = Test::Nginx->new()->plan(5)->write_file_expand('nginx.conf', <<'EOF');

%%TEST_GLOBALS%%

daemon off;

events {
}

http {
    %%TEST_GLOBALS_HTTP%%

    modsecurity_transaction_id "tid-HTTP-DEFAULT-$request_id";

    server {
        listen       127.0.0.1:8080;
        server_name  server1;

        location / {
            error_log %%TESTDIR%%/e_s1l1.log info;
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecDefaultAction "phase:1,log,deny,status:403"
                SecRule ARGS "@streq block403" "id:4,phase:1,status:403,block"
            ';
        }
    }

    server {
        listen       127.0.0.1:8080;
        server_name  server2;

        modsecurity_transaction_id "tid-SERVER-DEFAULT-$request_id";

        location / {
            error_log %%TESTDIR%%/e_s2l1.log info;
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecDefaultAction "phase:1,log,deny,status:403"
                SecRule ARGS "@streq block403" "id:4,phase:1,status:403,block"
            ';
        }

        location /specific {
            error_log %%TESTDIR%%/e_s2l2.log info;
            modsecurity on;
            modsecurity_transaction_id "tid-LOCATION-SPECIFIC-$request_id";
            modsecurity_rules '
                SecRuleEngine On
                SecDefaultAction "phase:1,log,deny,status:403"
                SecRule ARGS "@streq block403" "id:4,phase:1,status:403,block"
            ';
        }

        location /debuglog {
            modsecurity on;
            modsecurity_transaction_id "tid-DEBUG-$request_id";
            modsecurity_rules '
                SecRuleEngine On
                SecDebugLog %%TESTDIR%%/modsec_debug.log
                SecDebugLogLevel 4
                SecDefaultAction "phase:1,log,deny,status:403"
                SecRule ARGS "@streq block403" "id:4,phase:1,status:403,block"
            ';
        }

        location /auditlog {
            modsecurity on;
            modsecurity_transaction_id "tid-AUDIT-$request_id";
            modsecurity_rules '
                SecRuleEngine On
                SecDefaultAction "phase:1,log,deny,status:403"
                SecAuditEngine On
                SecAuditLogParts A
                SecAuditLog %%TESTDIR%%/modsec_audit.log
                SecAuditLogType Serial
                SecAuditLogStorageDir %%TESTDIR%%/
                SecRule ARGS "@streq block403" "id:4,phase:1,status:403,block"
            ';
        }
    }
}
EOF

$t->run();

###############################################################################

# charge limit_req

http(<<EOF);
GET /?what=block403 HTTP/1.0
Host: server1

EOF

isnt(lines($t, 'e_s1l1.log', 'unique_id "tid-HTTP-DEFAULT-'), 0, 'http default');

http(<<EOF);
GET /?what=block403 HTTP/1.0
Host: server2

EOF

isnt(lines($t, 'e_s2l1.log', 'unique_id "tid-SERVER-DEFAULT-'), 0, 'server default');

http(<<EOF);
GET /specific/?what=block403 HTTP/1.0
Host: server2

EOF

isnt(lines($t, 'e_s2l2.log', 'unique_id "tid-LOCATION-SPECIFIC-'), 0, 'location specific');

http(<<EOF);
GET /debuglog/?what=block403 HTTP/1.0
Host: server2

EOF

isnt(lines($t, 'modsec_debug.log', 'tid-DEBUG-'), 0, 'libmodsecurity debug log');

http(<<EOF);
GET /auditlog/?what=block403 HTTP/1.0
Host: server2

EOF

isnt(lines($t, 'modsec_audit.log', 'tid-AUDIT-'), 0, 'libmodsecurity audit log');

###############################################################################

sub lines {
	my ($t, $file, $pattern) = @_;
	my $path = $t->testdir() . '/' . $file;
	open my $fh, '<', $path or return "$!";
	my $value = map { $_ =~ /\Q$pattern\E/ } (<$fh>);
	close $fh;
	return $value;
}

###############################################################################
