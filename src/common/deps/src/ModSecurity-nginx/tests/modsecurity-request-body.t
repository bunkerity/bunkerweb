#!/usr/bin/perl

# (C) Andrei Belov

# Tests for ModSecurity-nginx connector (request body operations).

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

my $t = Test::Nginx->new()->has(qw/http proxy auth_request/);

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
        client_header_buffer_size 1024;

        location /bodyaccess {
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess On
                SecRule REQUEST_BODY "@rx BAD BODY" "id:11,phase:request,deny,log,status:403"
            ';
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location /nobodyaccess {
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess Off
                SecRule REQUEST_BODY "@rx BAD BODY" "id:21,phase:request,deny,log,status:403"
                SecRule ARGS_POST|ARGS_POST_NAMES "@rx BAD ARG" "id:22,phase:request,deny,log,status:403"
            ';
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location /bodylimitreject {
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess On
                SecRequestBodyLimit 128
                SecRequestBodyLimitAction Reject
                SecRule REQUEST_BODY "@rx BAD BODY" "id:31,phase:request,deny,log,status:403"
            ';
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location /bodylimitrejectserver {
            modsecurity off;
            proxy_pass http://127.0.0.1:%%PORT_8082%%;
        }

        location /bodylimitprocesspartial {
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess On
                SecRequestBodyLimit 128
                SecRequestBodyLimitAction ProcessPartial
                SecRule REQUEST_BODY "@rx BAD BODY" "id:41,phase:request,deny,log,status:403"
            ';
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }

        location = /auth {
            return 200;
        }

        location = /useauth {
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess On
            ';
            auth_request /auth;
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }
    }

    server {
        listen 127.0.0.1:%%PORT_8082%%;
        modsecurity on;
        modsecurity_rules '
            SecRuleEngine On
            SecRequestBodyAccess On
            SecRequestBodyLimit 128
            SecRequestBodyLimitAction Reject
            SecRule REQUEST_BODY "@rx BAD BODY" "id:31,phase:request,deny,log,status:403"
        ';
        location / {
            proxy_pass http://127.0.0.1:%%PORT_8081%%;
        }
    }
}
EOF

$t->run_daemon(\&http_daemon);
$t->run()->waitforsocket('127.0.0.1:' . port(8081));

$t->plan(40);

###############################################################################

foreach my $method (('GET', 'POST', 'PUT', 'DELETE')) {
like(http_req_body($method, '/bodyaccess', 'GOOD BODY'), qr/TEST-OK-IF-YOU-SEE-THIS/, "$method request body access on, pass");
like(http_req_body($method, '/bodyaccess', 'VERY BAD BODY'), qr/^HTTP.*403/, "$method request body access on, block");
like(http_req_body($method, '/nobodyaccess', 'VERY BAD BODY'), qr/TEST-OK-IF-YOU-SEE-THIS/, "$method request body access off, pass");
like(http_req_body_postargs($method, '/nobodyaccess', 'BAD ARG'), qr/TEST-OK-IF-YOU-SEE-THIS/, "$method request body access off (ARGS_POST), pass");
like(http_req_body($method, '/bodylimitreject', 'BODY' x 32), qr/TEST-OK-IF-YOU-SEE-THIS/, "$method request body limit reject, pass");
like(http_req_body($method, '/bodylimitreject', 'BODY' x 33), qr/^HTTP.*403/, "$method request body limit reject, block");
like(http_req_body($method, '/bodylimitprocesspartial', 'BODY' x 32 . 'BAD BODY'), qr/TEST-OK-IF-YOU-SEE-THIS/, "$method request body limit process partial, pass");
like(http_req_body($method, '/bodylimitprocesspartial', 'BODY' x 30 . 'BAD BODY' x 32), qr/^HTTP.*403/, "$method request body limit process partial, block");
}

like(http_req_body('POST', '/useauth', 'BODY' x 16), qr/TEST-OK-IF-YOU-SEE-THIS/, "POST with auth_request (request size < client_header_buffer_size)");
like(http_req_body('POST', '/useauth', 'BODY' x 257), qr/TEST-OK-IF-YOU-SEE-THIS/, "POST with auth_request (request size > client_header_buffer_size)");

like(
        http(
                'POST /useauth HTTP/1.0' . CRLF
                . 'Content-Length: 1028' . CRLF . CRLF
                . 'BODY' x 256,
                sleep => 0.1,
                body => 'BODY'
        ),
        qr/TEST-OK-IF-YOU-SEE-THIS/,
        'POST with auth_request (request size > client_header_buffer_size), no preread'
);

like(
        http(
                'POST /useauth HTTP/1.0' . CRLF
                . 'Content-Length: 64' . CRLF . CRLF
                . 'BODY' x 15,
                sleep => 0.1,
                body => 'BODY'
        ),
        qr/TEST-OK-IF-YOU-SEE-THIS/,
        'POST with auth_request (request size < client_header_buffer_size), no preread'
);

foreach my $method (('GET', 'POST', 'PUT', 'DELETE')) {
like(http_req_body($method, '/bodylimitrejectserver', 'BODY' x 33), qr/^HTTP.*403/, "$method request body limit reject, block (inherited SecRequestBodyLimit)");
}

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

sub http_req_body {
	my $method = shift;
	my $uri = shift;
	my $last = pop;
	return http( join '', (map {
		my $body = $_;
		"$method $uri HTTP/1.1" . CRLF
		. "Host: localhost" . CRLF
		. "Content-Length: " . (length $body) . CRLF . CRLF
		. $body
	} @_),
		"$method $uri HTTP/1.1" . CRLF
		. "Host: localhost" . CRLF
		. "Connection: close" . CRLF
		. "Content-Length: " . (length $last) . CRLF . CRLF
		. $last
	);
}

sub http_req_body_postargs {
	my $method = shift;
	my $uri = shift;
	my $last = pop;
	return http( join '', (map {
		my $body = $_;
		"$method $uri HTTP/1.1" . CRLF
		. "Host: localhost" . CRLF
		. "Content-Type: application/x-www-form-urlencoded" . CRLF
		. "Content-Length: " . (length "test=" . $body) . CRLF . CRLF
		. "test=" . $body
	} @_),
		"$method $uri HTTP/1.1" . CRLF
		. "Host: localhost" . CRLF
		. "Connection: close" . CRLF
		. "Content-Type: application/x-www-form-urlencoded" . CRLF
		. "Content-Length: " . (length "test=" . $last) . CRLF . CRLF
		. "test=" . $last
	);
}

###############################################################################
