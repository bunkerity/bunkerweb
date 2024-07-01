#!/usr/bin/perl

# (C) Andrei Belov

# Tests for ModSecurity-nginx connector (configuration merge).

###############################################################################

use warnings;
use strict;

use Test::More;
use Socket qw/ CRLF /;

BEGIN { use FindBin; chdir($FindBin::Bin); }

use lib 'lib';
use Test::Nginx;

###############################################################################

select STDERR; $| = 1;
select STDOUT; $| = 1;

my $t = Test::Nginx->new()->has(qw/http proxy/);

$t->write_file_expand('nginx.conf', <<'EOF');

%%TEST_GLOBALS%%

daemon off;

events {
}

http {
    %%TEST_GLOBALS_HTTP%%

    modsecurity on;
    modsecurity_rules '
        SecRuleEngine On
        SecRequestBodyAccess On
        SecRequestBodyLimit 128
        SecRequestBodyLimitAction Reject
        SecRule REQUEST_BODY "@rx BAD BODY" "id:11,phase:request,deny,log,status:403"
    ';

    server {
        listen       127.0.0.1:%%PORT_8080%%;
        server_name  localhost;

        location / {
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location /modsec-disabled {
            modsecurity_rules '
                SecRuleEngine Off
            ';
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location /nobodyaccess {
            modsecurity_rules '
                SecRequestBodyAccess Off
            ';
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location /bodylimitprocesspartial {
            modsecurity_rules '
                SecRequestBodyLimitAction ProcessPartial
            ';
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location /bodylimitincreased {
            modsecurity_rules '
                SecRequestBodyLimit 512
            ';
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location /server {
            modsecurity off;

            location /server/modsec-disabled {
                proxy_pass http://127.0.0.1:%%PORT_8082%%;
            }

            location /server/nobodyaccess {
                proxy_pass http://127.0.0.1:%%PORT_8083%%;
            }

            location /server/bodylimitprocesspartial {
                proxy_pass http://127.0.0.1:%%PORT_8084%%;
            }

            location /server/bodylimitincreased {
                proxy_pass http://127.0.0.1:%%PORT_8085%%;
            }
        }
    }

    server {
        listen 127.0.0.1:%%PORT_8082%%;

        modsecurity_rules '
                SecRuleEngine Off
        ';

        location / {
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }
    }

    server {
        listen 127.0.0.1:%%PORT_8083%%;

        modsecurity_rules '
                SecRequestBodyAccess Off
        ';

        location / {
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }
    }

    server {
        listen 127.0.0.1:%%PORT_8084%%;

        modsecurity_rules '
                SecRequestBodyLimitAction ProcessPartial
        ';

        location / {
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }
    }

    server {
        listen 127.0.0.1:%%PORT_8085%%;

        modsecurity_rules '
                SecRequestBodyLimit 512
        ';

        location / {
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }
    }
}
EOF

$t->run_daemon(\&http_daemon);
$t->run()->waitforsocket('127.0.0.1:' . port(8081));

$t->plan(10);

###############################################################################

like(http_get_body('/', 'GOOD BODY'), qr/TEST-OK-IF-YOU-SEE-THIS/, "http level defaults, pass");
like(http_get_body('/', 'VERY BAD BODY'), qr/^HTTP.*403/, "http level defaults, block");

like(http_get_body('/modsec-disabled', 'VERY BAD BODY'), qr/TEST-OK-IF-YOU-SEE-THIS/, "location override for SecRuleEngine, pass");
like(http_get_body('/nobodyaccess', 'VERY BAD BODY'), qr/TEST-OK-IF-YOU-SEE-THIS/, "location override for SecRequestBodyAccess, pass");
like(http_get_body('/bodylimitprocesspartial', 'BODY' x 33), qr/TEST-OK-IF-YOU-SEE-THIS/, "location override for SecRequestBodyLimitAction, pass");
like(http_get_body('/bodylimitincreased', 'BODY' x 64), qr/TEST-OK-IF-YOU-SEE-THIS/, "location override for SecRequestBodyLimit, pass");

like(http_get_body('/server/modsec-disabled', 'VERY BAD BODY'), qr/TEST-OK-IF-YOU-SEE-THIS/, "server override for SecRuleEngine, pass");
like(http_get_body('/server/nobodyaccess', 'VERY BAD BODY'), qr/TEST-OK-IF-YOU-SEE-THIS/, "server override for SecRequestBodyAccess, pass");
like(http_get_body('/server/bodylimitprocesspartial', 'BODY' x 33), qr/TEST-OK-IF-YOU-SEE-THIS/, "server override for SecRequestBodyLimitAction, pass");
like(http_get_body('/server/bodylimitincreased', 'BODY' x 64), qr/TEST-OK-IF-YOU-SEE-THIS/, "server override for SecRequestBodyLimit, pass");

###############################################################################

sub http_daemon {
	my $server = IO::Socket::INET->new(
		Proto => 'tcp',
		LocalHost => '127.0.0.1:' . port(8081),
		Listen => 5,
		Reuse => 1
	)
		or die "Can't create listening socket: $!\n";

	local $SIG{PIPE} = 'IGNORE';

	while (my $client = $server->accept()) {
		$client->autoflush(1);

		my $headers = '';
		my $uri = '';

		while (<$client>) {
			$headers .= $_;
			last if (/^\x0d?\x0a?$/);
		}

		$uri = $1 if $headers =~ /^\S+\s+([^ ]+)\s+HTTP/i;

		print $client <<'EOF';
HTTP/1.1 200 OK
Connection: close

EOF
		print $client "TEST-OK-IF-YOU-SEE-THIS"
			unless $headers =~ /^HEAD/i;

		close $client;
	}
}

sub http_get_body {
	my $uri = shift;
	my $last = pop;
	return http( join '', (map {
		my $body = $_;
		"GET $uri HTTP/1.1" . CRLF
		. "Host: localhost" . CRLF
		. "Content-Length: " . (length $body) . CRLF . CRLF
		. $body
	} @_),
		"GET $uri HTTP/1.1" . CRLF
		. "Host: localhost" . CRLF
		. "Connection: close" . CRLF
		. "Content-Length: " . (length $last) . CRLF . CRLF
		. $last
	);
}

###############################################################################
