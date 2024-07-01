#!/usr/bin/perl

# (C) Andrei Belov

# Tests for ModSecurity-nginx connector (request body operations, HTTP/2).

###############################################################################

use warnings;
use strict;

use Test::More;
use Socket qw/ CRLF /;

BEGIN { use FindBin; chdir($FindBin::Bin); }

use lib 'lib';
use Test::Nginx;
use Test::Nginx::HTTP2;

###############################################################################

select STDERR; $| = 1;
select STDOUT; $| = 1;

my $t = Test::Nginx->new()->has(qw/http http_v2 proxy auth_request/);

$t->write_file_expand('nginx.conf', <<'EOF');

%%TEST_GLOBALS%%

daemon off;

events {
}

http {
    %%TEST_GLOBALS_HTTP%%

    server {
        listen 127.0.0.1:8081;
        location / {
            return 200 "TEST-OK-IF-YOU-SEE-THIS";
        }
    }

    server {
        listen       127.0.0.1:8080 http2;
        server_name  localhost;

        modsecurity on;
        client_header_buffer_size 1024;

        location /bodyaccess {
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess On
                SecRule REQUEST_BODY "@rx BAD BODY" "id:11,phase:request,deny,log,status:403"
            ';
            proxy_pass http://127.0.0.1:8081;
        }

        location /nobodyaccess {
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess Off
                SecRule REQUEST_BODY "@rx BAD BODY" "id:21,phase:request,deny,log,status:403"
                SecRule ARGS_POST|ARGS_POST_NAMES "@rx BAD ARG" "id:22,phase:request,deny,log,status:403"
            ';
            proxy_pass http://127.0.0.1:8081;
        }

        location /bodylimitreject {
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess On
                SecRequestBodyLimit 128
                SecRequestBodyLimitAction Reject
                SecRule REQUEST_BODY "@rx BAD BODY" "id:31,phase:request,deny,log,status:403"
            ';
            proxy_pass http://127.0.0.1:8081;
        }

        location /bodylimitprocesspartial {
            modsecurity_rules '
                SecRuleEngine On
                SecRequestBodyAccess On
                SecRequestBodyLimit 128
                SecRequestBodyLimitAction ProcessPartial
                SecRule REQUEST_BODY "@rx BAD BODY" "id:41,phase:request,deny,log,status:403"
            ';
            proxy_pass http://127.0.0.1:8081;
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
            proxy_pass http://127.0.0.1:8081;
        }
    }
}
EOF

$t->run();

$t->plan(36);

###############################################################################

my ($s, $sid, $frames, $frame);

foreach my $method (('GET', 'POST', 'PUT', 'DELETE')) {

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => $method, path => '/bodyaccess', 'body_more' => 1 });
$s->h2_body('GOOD BODY');
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "${method} request body access on, pass");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => $method, path => '/bodyaccess', 'body_more' => 1 });
$s->h2_body('VERY BAD BODY');
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "HEADERS" } @$frames;
is($frame->{headers}->{':status'}, 403, "${method} request body access on, block");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => $method, path => '/nobodyaccess', 'body_more' => 1 });
$s->h2_body('VERY BAD BODY');
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "${method} request body access off, pass");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ 'body_more' => 1,
	headers => [
		{name => ':method', value => "${method}" },
		{name => ':scheme', value => 'http' },
		{name => ':path', value => '/nobodyaccess' },
		{name => 'host', value => 'localhost' },
		{name => 'content-type', value => 'application/x-www-form-urlencoded' }
	] });
$s->h2_body('test=VERY BAD BODY');
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "${method} request body access off (ARGS_POST), pass");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => $method, path => '/bodylimitreject', 'body_more' => 1 });
$s->h2_body('BODY' x 32);
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "${method} request body limit reject, pass");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => $method, path => '/bodylimitreject', 'body_more' => 1 });
$s->h2_body('BODY' x 33);
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "HEADERS" } @$frames;
is($frame->{headers}->{':status'}, 403, "${method} request body limit reject, block");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => $method, path => '/bodylimitprocesspartial', 'body_more' => 1 });
$s->h2_body('BODY' x 32 . 'BAD BODY');
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "${method} request body limit process partial, pass");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => $method, path => '/bodylimitprocesspartial', 'body_more' => 1 });
$s->h2_body('BODY' x 30 . 'BAD BODY' x 32);
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "HEADERS" } @$frames;
is($frame->{headers}->{':status'}, 403, "${method} request body limit process partial, block");

}

TODO: {
# https://github.com/SpiderLabs/ModSecurity-nginx/issues/163
# https://github.com/nginx/nginx/commit/6c89d752c8ab3a3cc0832927484808b68153f8c4
local $TODO = 'not yet' unless $t->has_version('1.19.3');

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => 'POST', path => '/useauth', 'body' => 'BODY' x 16 });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "POST with auth_request (request size < client_header_buffer_size)");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => 'POST', path => '/useauth', 'body' => 'BODY' x 257 });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "POST with auth_request (request size > client_header_buffer_size)");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => 'POST', path => '/useauth', 'body_more' => 1 });
$s->h2_body('BODY' x 15, { 'body_more' => 1 });
select undef, undef, undef, 0.1;
$s->h2_body('BODY');
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "POST with auth_request (request size < client_header_buffer_size), no preread");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ method => 'POST', path => '/useauth', 'body_more' => 1 });
$s->h2_body('BODY' x 256, { 'body_more' => 1 });
select undef, undef, undef, 0.1;
$s->h2_body('BODY');
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/TEST-OK-IF-YOU-SEE-THIS/, "POST with auth_request (request size > client_header_buffer_size), no preread");

}

###############################################################################
